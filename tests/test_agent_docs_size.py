"""Agent docs stay within the size rule (SPEC-0018, DT-013, DEC-004).

Every ``.agent_docs/*.md`` holds at most 220 lines: 20 lines of slack over the 200 line rule make the test a
trigger for consolidation, not a blocker for every edit.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENT_DOCS = sorted((REPO / ".agent_docs").glob("*.md"))
MAX_LINES = 220


def oversized_docs(paths: list[Path], limit: int) -> list[str]:
    """Return ``<name>: <count> lines`` for each file holding more than ``limit`` lines."""
    counts = ((path.name, len(path.read_text(encoding="utf-8").splitlines())) for path in paths)
    return [f"{name}: {count} lines" for name, count in counts if count > limit]


def test_agent_docs_stay_within_the_size_rule() -> None:
    assert AGENT_DOCS, "no .agent_docs/*.md found"
    oversized = oversized_docs(AGENT_DOCS, MAX_LINES)
    assert oversized == [], f"agent docs above {MAX_LINES} lines: {', '.join(oversized)}"


def test_the_guard_names_each_oversized_file(tmp_path: Path) -> None:
    long_doc = tmp_path / "long.md"
    long_doc.write_text("line\n" * 5, encoding="utf-8")
    short_doc = tmp_path / "short.md"
    short_doc.write_text("line\n", encoding="utf-8")
    assert oversized_docs([long_doc, short_doc], 4) == ["long.md: 5 lines"]
