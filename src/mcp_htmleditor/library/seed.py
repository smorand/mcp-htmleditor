"""The initial content of a new library (SPEC-0025, DEC-036): a manifest and the two conference decks, copied unchanged.

``seed_if_new`` runs once, on the first start of a library, and the fact is remembered in ``meta('seeded')``: a later
start neither adds nor resets anything, even when every folder was deleted. Nothing is created unless every file of the
manifest matches its size and its sha256, and the seeding writes no activity line.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..tracing import trace_span
from .store import Library

logger = logging.getLogger(__name__)

MANIFEST_NAME: Final = "manifest.json"
TIME_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
READ_BLOCK: Final = 1 << 20


class SeedError(RuntimeError):
    """The seed cannot be applied: the manifest or a file is missing, unreadable or not what the manifest says."""


@dataclass(frozen=True, slots=True)
class SeedPresentation:
    """One verified presentation of the seed: its name, its source file and the modified time it keeps."""

    name: str
    source: Path
    modified: float


def seed_if_new(library: Library, seed_dir: Path, clock: Callable[[], float]) -> bool:
    """Create the initial content when the library was never seeded; return whether it did.

    Verifies every file of ``<seed_dir>/manifest.json`` (size and sha256) before anything is written, then lets the
    library create the folder, its member and the presentations in one transaction. ``SeedError`` leaves nothing.
    Time O(total bytes) for the hashes, paid only on the first start.
    """
    if library.is_seeded():
        return False
    folder, members, presentations = _read_manifest(seed_dir)
    with trace_span("library.seed", {"presentations": len(presentations)}):
        created = library.seed_initial_content(folder, members, presentations, clock)
    if created:
        logger.info("Created the initial content: %d presentations", len(presentations))
    return created


def _read_manifest(seed_dir: Path) -> tuple[str, list[tuple[str, str]], list[SeedPresentation]]:
    try:
        manifest = json.loads((seed_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        folder = str(manifest["folder"])
        members = [(str(member["email"]), str(member["role"])) for member in manifest["members"]]
        presentations = [_verified(seed_dir, entry) for entry in manifest["presentations"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SeedError(f"the seed in {seed_dir} is unreadable: {type(exc).__name__}") from exc
    return folder, members, presentations


def _verified(seed_dir: Path, entry: dict[str, object]) -> SeedPresentation:
    source = seed_dir / str(entry["file"])
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as handle:
        while block := handle.read(READ_BLOCK):
            digest.update(block)
            size += len(block)
    if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
        raise SeedError(f"the seed file {source.name} does not match its manifest")
    modified = dt.datetime.strptime(str(entry["modified"]), TIME_FORMAT).replace(tzinfo=dt.UTC).timestamp()
    return SeedPresentation(str(entry["name"]), source, modified)
