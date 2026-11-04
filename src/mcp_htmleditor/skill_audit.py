"""Size and budget audit of the progressive skill, for `mcp-htmleditor skill-audit`.

Every item (the core, then each topic in index order) is rendered through the same
``*_output()`` methods as the `skill` command, so the measured size is the byte count
the command writes on the standard output.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

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


def run_audit(library: SkillLibrary) -> AuditReport:
    """Measure the core then every topic; a missing or oversized item is a problem, never a stop."""
    items: list[AuditItem] = []
    problems: list[str] = []
    measures: list[tuple[str, str, int, Callable[[], str]]] = [
        (CORE_NAME, CORE_NAME, CORE_BUDGET_BYTES, library.core_output)
    ]
    measures += [
        (topic.name, f"topic {topic.name}", TOPIC_BUDGET_BYTES, partial(library.topic_output, topic.name))
        for topic in TOPICS
    ]
    for name, label, budget, render in measures:
        try:
            size = len(render().encode("utf-8"))
        except NotInstalledError:
            items.append(AuditItem(name, None, None, budget, STATUS_MISSING))
            problems.append("core is not installed" if name == CORE_NAME else f'topic "{name}" is not installed')
            continue
        is_over = size > budget
        items.append(AuditItem(name, size, -(-size // TOKEN_DIVISOR), budget, STATUS_OVER if is_over else STATUS_OK))
        if is_over:
            problems.append(f"{label} is over its budget ({size} > {budget})")
    return AuditReport(tuple(items), tuple(problems))


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
