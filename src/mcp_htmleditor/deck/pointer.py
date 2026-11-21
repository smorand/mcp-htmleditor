"""``mcp-htmleditor add-pointer``: give an older presentation the pointer of SPEC-0017 (SPEC-0034).

A deck created before the pointer has no pointer code, no ``Pointeur`` control and no ``L`` key. The three parts
are inserted as text, only the missing ones, so the rest of the author's file stays byte for byte as it was:
the code block copied from the Carbon bootstrap (the single source, ``tools/sync_deck_pointer.py``), a control
cloned from the deck's own ``btn-present`` and a small key script. Raises ``DeckError``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ..fileio import atomic_write
from ..templates import _repo_templates_dir
from ..tracing import trace_span
from . import DeckError, require_encodable_path
from .patch import TEMPLATE_FOLDERS

logger = logging.getLogger(__name__)

BEGIN = "<!-- deck-pointer:begin -->"
END = "<!-- deck-pointer:end -->"
HISTORY_REASON = "add-pointer"
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
KEY_TEST = re.compile(r"""\.key\s*===?\s*['"][lL]['"]""")
PRESENT_BUTTON = re.compile(r"""<button\b[^>]*(?<![\w-])id=["']btn-present["'][^>]*>.*?</button>""", re.DOTALL)
CLASS_ATTR = re.compile(r"""\bclass=("[^"]*"|'[^']*')""")
CONTROL_TITLE = "Présenter avec le pointeur (L)"
KEY_SCRIPT = """<script id="deck-pointer-key">
  document.addEventListener('keydown', function (e) {
    var ae = document.activeElement;
    if (ae && (ae.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName))) return;
    if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();
  });
</script>"""


@dataclass(frozen=True, slots=True)
class PointerOutcome:
    """What a run did: the file as given and whether any part was added."""

    file: str
    added: bool

    def summary(self) -> str:
        """The one line the command prints."""
        return f"{self.file}: pointer added" if self.added else f"{self.file}: already has the pointer"


def add_pointer(file: str) -> PointerOutcome:
    """Add the missing parts of the pointer to the presentation at ``file``; see the module doc.

    Checks run in this order before any write: path, file exists, not a template file, UTF-8, a presentation,
    a ``Présenter`` control when the control is missing. Time O(n) for a deck of n characters.
    """
    with trace_span("deck.add_pointer", {"file.path": file}) as span:
        outcome = _add(file)
        span.set_attribute("pointer.added", outcome.added)
    logger.debug("add-pointer %s: %s", file, outcome.summary())
    return outcome


def _add(file: str) -> PointerOutcome:
    require_encodable_path(file)
    deck = Path(file)
    if not deck.is_file():
        raise DeckError(f"File not found: {file}")
    if _is_template(deck):
        raise DeckError(f"Refusing to modify a template: {file}")
    try:
        text = deck.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise DeckError(f"File is not valid UTF-8: {file}") from None
    if 'data-type="slide"' not in text:
        raise DeckError(f"{file} is not a presentation")
    seen = COMMENT.sub("", text)
    need_code = '<script id="deck-pointer-script"' not in seen
    need_control = 'id="btn-pointer"' not in seen
    need_key = 'id="deck-pointer-key"' not in seen and not KEY_TEST.search(seen)
    if not (need_code or need_control or need_key):
        return PointerOutcome(file, False)
    eol = "\r\n" if "\r\n" in text else "\n"
    if need_control:
        text = _with_control(text, file, eol)
    if need_code or need_key:
        parts = ([_source_block()] if need_code else []) + ([KEY_SCRIPT] if need_key else [])
        text = _with_code(text, eol.join(parts).replace("\r\n", "\n").replace("\n", eol), eol)
    atomic_write(deck, text, reason=HISTORY_REASON)
    return PointerOutcome(file, True)


def _is_template(deck: Path) -> bool:
    parts = tuple(part.casefold() for part in deck.resolve().parts)
    return any(parts[i : i + len(folder)] == folder for folder in TEMPLATE_FOLDERS for i in range(len(parts)))


def _source_block() -> str:
    """The pointer code of the Carbon bootstrap, markers included."""
    source = (_repo_templates_dir() / "bootstrap" / "slides-empty.html").read_text(encoding="utf-8")
    start = source.index(BEGIN)
    return source[start : source.index(END, start) + len(END)]


def _with_control(text: str, file: str, eol: str) -> str:
    match = PRESENT_BUTTON.search(_blank_comments(text))
    if match is None:
        raise DeckError(f"{file} has no Présenter control, nothing to place the Pointeur control after")
    opening = text[match.start() : text.index(">", match.start()) + 1]
    cls = CLASS_ATTR.search(opening)
    klass = f" class={cls.group(1)}" if cls else ""
    line_start = text.rfind("\n", 0, match.start()) + 1
    indent = re.match(r"[ \t]*", text[line_start : match.start()])
    pad = indent.group(0) if indent else ""
    control = (
        f'<button{klass} id="btn-pointer" onclick="presentWithPointer()" title="{CONTROL_TITLE}" '
        f'aria-label="{CONTROL_TITLE}" style="width:auto;padding:0 12px">Pointeur</button>'
    )
    return text[: match.end()] + eol + pad + control + text[match.end() :]


def _blank_comments(text: str) -> str:
    """``text`` with every HTML comment replaced by spaces: same length, so offsets stay valid in ``text``."""
    return COMMENT.sub(lambda m: " " * len(m.group(0)), text)


def _with_code(text: str, code: str, eol: str) -> str:
    """Put ``code`` before the last ``</body>`` (at the end of the file when there is none)."""
    close = _blank_comments(text).lower().rfind("</body>")
    if close < 0:
        return text + eol + code + eol
    return text[:close] + code + eol + text[close:]
