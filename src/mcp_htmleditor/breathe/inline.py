"""``mcp-htmleditor breathe-inline``: embed or link the decoration and pictures of a Breathe deck (SPEC-0023 DEC-009).

A deck's ``<style>`` holds a decoration block between ``/* breathe:assets:begin */`` and ``/* breathe:assets:end */``.
Every ``med-bg-<x>`` class used after that style gets a rule whose background is ``bg-<x>.png``, every
``med-ico-<x>`` class one whose background is ``icon-<x>.png``, and every ``<img data-asset="<name>">`` gets its
``src``: the picture as a data URI (inline) or ``assets/<name>`` (link, missing files copied next to the deck).
Files come from the deck's ``assets`` folder first, then the catalogue shipped with the editor.

Every check runs before any asset is read, copied or the deck written (spec FR-NEW-008 order): missing deck,
template file, UTF-8, block, asset names, links leaving ``assets``, files not found. Raises ``DeckError``.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..deck import DeckError, require_encodable_path
from ..deck.patch import TEMPLATE_FOLDERS
from ..fileio import atomic_write
from ..templates import _repo_templates_dir
from ..tracing import trace_span

logger = logging.getLogger(__name__)

BEGIN = "/* breathe:assets:begin */"
END = "/* breathe:assets:end */"
CLASS_FILES = (("med-bg-", "bg-"), ("med-ico-", "icon-"))
ASSETS = "assets"
HISTORY_REASON = "breathe-inline"
PLAIN_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
CLASS_ATTR = re.compile(r'\bclass="([^"]*)"')
ASSET_IMG = re.compile(r'<img\b[^>]*\bdata-asset="([^"]*)"[^>]*>')
SRC_ATTR = re.compile(r'\ssrc="[^"]*"')


@dataclass(frozen=True, slots=True)
class InlineOutcome:
    """What a run wrote: the classes and pictures, the files copied (link mode), the folder and the size."""

    file: str
    link: bool
    classes: int
    pictures: int
    copied: int
    folder: Path
    size_kb: int

    def summary(self) -> str:
        """The one line the command prints (spec FR-NEW-006, FR-NEW-007)."""
        head = f"{self.file}: {self.classes} background and icon classes, {self.pictures} pictures"
        if self.link:
            return f"{head} linked, {self.copied} files copied to {self.folder}, {self.size_kb} KB"
        return f"{head} embedded, {self.size_kb} KB"


@dataclass(frozen=True, slots=True)
class _Need:
    """One asset the deck needs: the name as written, the file it maps to, where it was first written."""

    name: str
    file_name: str
    position: int


def catalogue_dir() -> Path:
    """The Breathe catalogue shipped with the installed editor (never the user's templates folder)."""
    return _repo_templates_dir() / ASSETS / "breathe"


def embed_assets(file: str, *, link: bool = False, allow_template: bool = False) -> InlineOutcome:
    """Embed (or link) every decoration class and named picture of the deck at ``file``; see the module doc.

    ``allow_template`` is for the maintainer tool that refreshes the shipped Breathe files. Time O(n + k·s) for a
    deck of n characters and k needed assets of s bytes; the deck is held once in memory.
    """
    with trace_span("breathe.inline", {"file.path": file, "breathe.link": link}) as span:
        outcome = _embed(file, link, allow_template)
        span.set_attribute("breathe.classes", outcome.classes)
        span.set_attribute("breathe.pictures", outcome.pictures)
    logger.debug("breathe-inline %s: %s", file, outcome.summary())
    return outcome


def _embed(file: str, link: bool, allow_template: bool) -> InlineOutcome:
    require_encodable_path(file)
    deck = Path(file)
    if not deck.is_file():
        raise DeckError(f"File not found: {file}")
    if not allow_template and _is_template(deck):
        raise DeckError(f"Refusing to modify a template: {file}")
    try:
        text = deck.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise DeckError(f"File is not valid UTF-8: {file}") from None
    begin = text.find(BEGIN)
    end = text.find(END, begin) if begin >= 0 else -1
    if begin < 0 or end < 0:
        raise DeckError(f"{file} has no breathe:assets block in its <style>")
    style_end = text.find("</style>", end)
    body_start = style_end if style_end >= 0 else end
    classes, pictures = _needs(text, body_start)
    folder = deck.resolve().parent / ASSETS
    catalogue = catalogue_dir()
    needs = sorted([*classes.values(), *pictures], key=lambda need: need.position)
    _check_names(needs)
    _check_links(needs, folder)
    sources = _locate(needs, folder, catalogue)
    rules = [_rule(cls, need.file_name, sources, link) for cls, need in sorted(classes.items())]
    block = BEGIN + "\n" + "\n".join(rules) + "\n  " + END
    html = text[:begin] + block + text[end + len(END) :]
    html = _fill_pictures(html, sources, link)
    copied = _copy_missing(sources, folder) if link else []
    try:
        atomic_write(deck, html, reason=HISTORY_REASON)
    except DeckError:
        for path in copied:
            path.unlink(missing_ok=True)
        raise
    size = len(html.encode("utf-8")) // 1024
    return InlineOutcome(file, link, len(classes), len(pictures), len(copied), folder, size)


def _is_template(deck: Path) -> bool:
    parts = tuple(part.casefold() for part in deck.resolve().parts)
    return any(parts[i : i + len(folder)] == folder for folder in TEMPLATE_FOLDERS for i in range(len(parts)))


def _needs(text: str, body_start: int) -> tuple[dict[str, _Need], list[_Need]]:
    """The decoration classes used after the deck's style (first occurrence kept) and every named picture."""
    classes: dict[str, _Need] = {}
    for match in CLASS_ATTR.finditer(text, body_start):
        for cls in match.group(1).split():
            for prefix, file_prefix in CLASS_FILES:
                if cls.startswith(prefix) and cls not in classes:
                    suffix = cls[len(prefix) :]
                    classes[cls] = _Need(suffix, f"{file_prefix}{suffix}.png", match.start())
    pictures = [_Need(m.group(1), m.group(1), m.start()) for m in ASSET_IMG.finditer(text, body_start)]
    return classes, pictures


def _check_names(needs: list[_Need]) -> None:
    for need in needs:
        if not PLAIN_NAME.fullmatch(need.name):
            raise DeckError(f"asset name {need.name} is not a plain file name")


def _check_links(needs: list[_Need], folder: Path) -> None:
    """A file of the deck's assets folder (or a link there, dangling or not) must resolve inside that folder."""
    root = folder.resolve()
    for need in needs:
        candidate = folder / need.file_name
        if (candidate.is_symlink() or candidate.exists()) and not candidate.resolve().is_relative_to(root):
            raise DeckError(f"asset {need.file_name} leads outside {folder}")


def _locate(needs: list[_Need], folder: Path, catalogue: Path) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for need in needs:
        if need.file_name in sources:
            continue
        for base in (folder, catalogue):
            if (base / need.file_name).is_file():
                sources[need.file_name] = base / need.file_name
                break
        else:
            raise DeckError(f"asset {need.file_name} not found in: {folder}, {catalogue}")
    return sources


def _uri(file_name: str, sources: dict[str, Path], link: bool) -> str:
    if link:
        return f"{ASSETS}/{file_name}"
    path = sources[file_name]
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _rule(cls: str, file_name: str, sources: dict[str, Path], link: bool) -> str:
    return f"  .{cls} {{ background-image:url({_uri(file_name, sources, link)}); }}"


def _fill_pictures(html: str, sources: dict[str, Path], link: bool) -> str:
    cache: dict[str, str] = {}

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        uri = cache.setdefault(name, _uri(name, sources, link))
        tag = match.group(0)
        if SRC_ATTR.search(tag):
            return SRC_ATTR.sub(lambda _m: f' src="{uri}"', tag, count=1)
        return tag.replace("<img", f'<img src="{uri}"', 1)

    return ASSET_IMG.sub(fill, html)


def _copy_missing(sources: dict[str, Path], folder: Path) -> list[Path]:
    """Copy into the deck's assets folder every needed file found only in the catalogue; never overwrite."""
    copied: list[Path] = []
    for name, source in sources.items():
        target = folder / name
        if source.parent == folder or target.exists() or target.is_symlink():
            continue
        try:
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        except OSError as exc:
            for path in copied:
                path.unlink(missing_ok=True)
            raise DeckError(f"Cannot write {target}: {exc.strerror or exc}") from None
        copied.append(target)
    return copied
