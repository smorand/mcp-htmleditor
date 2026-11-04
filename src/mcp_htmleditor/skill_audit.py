"""Size and budget audit of the progressive skill, for `mcp-htmleditor skill-audit`.

Every item (the core, then each topic in index order) is rendered through the same
``*_output()`` methods as the `skill` command, so the measured size is the byte count
the command writes on the standard output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from .skill_content import (
    CORE_BUDGET_BYTES,
    TOPIC_BUDGET_BYTES,
    TOPICS,
    NotInstalledError,
    SkillLibrary,
)

CORE_NAME = "core"
TOKEN_DIVISOR = 4

STATUS_OK = "OK"
STATUS_OVER = "OVER"
STATUS_MISSING = "MISSING"

TOOLS_HEADING = "## Tools"
_TOOL_LINE = re.compile(r"-\s+([\w-]+):")
_FENCE_OPEN = re.compile(r"[ \t]*(`{3,}|~{3,})")

# Stale statements in list order; every one is scanned on the text without fenced blocks, except
# `git commit` which is also wanted inside a code block (a commit forced by the skill).
STALE_STATEMENTS = ("GrapesJS", "6 outils", "15 types", "localhost:7842", "git commit", "Défauts d'export mesurés")
UNSTRIPPED_STATEMENTS = frozenset({"git commit"})
_COUNT_PATTERN = re.compile(r"(?<!\w)\d+\s+(?:outils|tools)(?!\w)", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class AuditItem:
    name: str  # "core" or the topic name
    size_bytes: int | None
    tokens: int | None  # ceil(size_bytes / 4)
    budget: int
    status: str  # "OK" | "OVER" | "MISSING"


@dataclass(frozen=True, slots=True)
class AuditReport:
    items: tuple[AuditItem, ...]
    problems: tuple[str, ...]  # text after "PROBLEM "

    @property
    def verdict(self) -> str:
        return STATUS_OK if not self.problems else "FAIL"


def run_audit(library: SkillLibrary, tool_names: Sequence[str] = (), routing_text: str | None = None) -> AuditReport:
    """Measure the core then every topic, then check tools and stale statements.

    A missing or oversized item is a problem, never a stop. Problems come in this order: per item,
    tool list, stale statements (core, topics, routing skill), routing skill not found.
    """
    items: list[AuditItem] = []
    problems: list[str] = []
    texts: dict[str, str] = {}
    measures: list[tuple[str, str, int, Callable[[], str]]] = [
        (CORE_NAME, CORE_NAME, CORE_BUDGET_BYTES, library.core_output)
    ]
    measures += [
        (topic.name, f"topic {topic.name}", TOPIC_BUDGET_BYTES, partial(library.topic_output, topic.name))
        for topic in TOPICS
    ]
    for name, label, budget, render in measures:
        try:
            text = render()
        except NotInstalledError:
            items.append(AuditItem(name, None, None, budget, STATUS_MISSING))
            problems.append("core is not installed" if name == CORE_NAME else f'topic "{name}" is not installed')
            continue
        texts[name] = text
        size = len(text.encode("utf-8"))
        is_over = size > budget
        items.append(AuditItem(name, size, -(-size // TOKEN_DIVISOR), budget, STATUS_OVER if is_over else STATUS_OK))
        if is_over:
            problems.append(f"{label} is over its budget ({size} > {budget})")
    if CORE_NAME in texts:
        problems += _tool_problems(listed_tools(texts[CORE_NAME]), tool_names)
    locations = [(name, f"in {'core' if name == CORE_NAME else 'topic ' + name}") for name in texts]
    problems += [
        f'stale statement "{statement}" {where}'
        for name, where in locations
        for statement in find_stale(texts[name], include_counts=name == CORE_NAME)
    ]
    if routing_text is None:
        problems.append("routing skill not found")
    else:
        problems += [
            f'stale statement "{statement}" in routing skill'
            for statement in find_stale(routing_text, include_counts=True)
        ]
    return AuditReport(tuple(items), tuple(problems))


def listed_tools(core_text: str) -> list[str]:
    """Names at the start of the `- <name>:` lines of the `## Tools` section (up to the next `## ` heading)."""
    names: list[str] = []
    is_inside = False
    for line in core_text.splitlines():
        if line.startswith("## "):
            is_inside = line.rstrip() == TOOLS_HEADING
            continue
        match = _TOOL_LINE.match(line) if is_inside else None
        if match:
            names.append(match.group(1))
    return names


def strip_fenced_blocks(text: str) -> str:
    """Blank the ``` and ~~~ fenced blocks (fences included); an unclosed fence runs to the end."""
    out: list[str] = []
    fence = ""
    for line in text.splitlines(keepends=True):
        if fence:
            closing = line.strip()
            if closing and set(closing) == {fence[0]} and len(closing) >= len(fence):
                fence = ""
            out.append(_blank(line))
            continue
        opening = _FENCE_OPEN.match(line)
        if opening:
            fence = opening.group(1)
            out.append(_blank(line))
            continue
        out.append(line)
    return "".join(out)


def find_stale(text: str, *, include_counts: bool) -> list[str]:
    """Stale statements found in text (lower case, list order then counts), once per distinct statement."""
    stripped = strip_fenced_blocks(text)
    found: dict[str, str] = {}
    for statement, pattern in _STALE_PATTERNS:
        match = pattern.search(text if statement in UNSTRIPPED_STATEMENTS else stripped)
        if match:
            found.setdefault(normalized := _WHITESPACE.sub(" ", match.group(0).lower()), normalized)
    if include_counts:
        for match in _COUNT_PATTERN.finditer(stripped):
            found.setdefault(normalized := _WHITESPACE.sub(" ", match.group(0).lower()), normalized)
    return list(found.values())


def source_routing_skill_path() -> Path:
    """Routing skill of the source tree this module runs from, whatever the current directory."""
    return Path(__file__).resolve().parents[2] / "dynamic-skills" / "html-editor" / "SKILL.md"


def read_routing_skill(installed: Path, source: Path) -> str | None:
    """Text of the installed routing skill, else of the source one; None when neither exists."""
    for path in (installed, source):
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


def _tool_problems(listed: Sequence[str], provided: Sequence[str]) -> list[str]:
    provided_set, listed_set = set(provided), set(listed)
    problems = [
        f'tool "{name}" is listed in the core but does not exist' for name in listed if name not in provided_set
    ]
    problems += [f'tool "{name}" exists but is not listed in the core' for name in provided if name not in listed_set]
    return problems


def _blank(line: str) -> str:
    return "\n" if line.endswith("\n") else ""


def _stale_pattern(statement: str) -> re.Pattern[str]:
    words = (re.escape(word).replace("\\'", "['’]").replace("'", "['’]") for word in statement.split())
    return re.compile(rf"(?<!\w){r'\s+'.join(words)}(?!\w)", re.IGNORECASE)


_STALE_PATTERNS = tuple((statement, _stale_pattern(statement)) for statement in STALE_STATEMENTS)


def format_text(report: AuditReport) -> str:
    lines = [_item_line(item) for item in report.items]
    lines += [f"PROBLEM {problem}" for problem in report.problems]
    count = len(report.problems)
    if count:
        lines.append(f"skill-audit: FAIL ({count} problem{'s' if count > 1 else ''})")
    else:
        lines.append("skill-audit: OK")
    return "\n".join(lines) + "\n"


def format_json(report: AuditReport) -> str:
    payload = {
        "items": [
            {
                "name": item.name,
                "bytes": item.size_bytes,
                "tokens": item.tokens,
                "budget": item.budget,
                "status": item.status,
            }
            for item in report.items
        ],
        "problems": list(report.problems),
        "verdict": report.verdict,
    }
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _item_line(item: AuditItem) -> str:
    if item.status == STATUS_MISSING:
        return f"{item.name}: MISSING"
    return f"{item.name}: {item.size_bytes} bytes, ~{item.tokens} tokens (budget {item.budget}) {item.status}"
