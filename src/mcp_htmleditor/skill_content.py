"""Progressive skill output for `mcp-htmleditor skill`.

The skill is a core (``core.md``) plus one file per topic (``topics/<topic>.md``).
:class:`SkillLibrary` renders the exact stdout text of the core, of one topic or
of everything; failures are :class:`SkillError` subclasses carrying the message
and the exit status the CLI reports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import arch_checks, config


@dataclass(frozen=True, slots=True)
class Topic:
    name: str
    description: str  # exact text of the index in core.md


TOPICS: tuple[Topic, ...] = (
    Topic("create", "Create and edit a file: workflows, rules for text, slides and images"),
    Topic("export", "Export to PPTX and DOCX: what is kept, approximated, lost"),
    Topic("templates", "Build a template from an existing PPTX or DOCX"),
    Topic("slides-carbon", "Rules for IBM Carbon slides"),
    Topic("slides-ei", "Rules for Euro-Information slides"),
    Topic(
        "medical",
        "Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget",
    ),
    Topic("medical-sources", "Medical slides: citing sources and anonymising patient images"),
    Topic("document", "Rules for Word-like documents and their DOCX export"),
    Topic("mail", "Rules for HTML mails"),
    Topic("website", "Rules for single page websites"),
    Topic("gantt", "Rules for Gantt charts"),
    Topic("arch-diagram", "Rules for architecture diagrams"),
    Topic("arch-qa", "Visual quality review of architecture diagrams and its checklist"),
    Topic("annotated-image", "Rules for annotated images"),
    Topic("tables", "Rules for tables"),
)
TOPIC_NAMES: tuple[str, ...] = tuple(topic.name for topic in TOPICS)

CORE_BUDGET_BYTES = 7000
TOPIC_BUDGET_BYTES = 8000

CORE_FILENAME = "core.md"
TOPICS_DIRNAME = "topics"

UNKNOWN_TOPIC_EXIT = 2
NOT_INSTALLED_EXIT = 1

BOTH_OPTIONS_MESSAGE = "Error: --type and --all cannot be used together"
CORE_NOT_INSTALLED_MESSAGE = "Skill core is not installed"
UNKNOWN_TOPIC_TEMPLATE = 'Unknown skill topic "{topic}". Valid topics: {valid}'
TOPIC_NOT_INSTALLED_TEMPLATE = 'Skill topic "{topic}" is not installed'
CHECKLIST_NOT_INSTALLED_TEMPLATE = 'Skill topic "{topic}" has no checklist installed'
CHECKLIST_TOPIC = "arch-qa"


class SkillError(Exception):
    """A skill request that cannot be served: message for stderr, exit status for the CLI."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownTopicError(SkillError):
    exit_code = UNKNOWN_TOPIC_EXIT


class NotInstalledError(SkillError):
    exit_code = NOT_INSTALLED_EXIT


@dataclass(frozen=True, slots=True)
class SkillLibrary:
    skill_dir: Path
    read_checklist: Callable[[], str]

    def core_output(self) -> str:
        """Return the core, stripped, with one final newline."""
        try:
            text = (self.skill_dir / CORE_FILENAME).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise NotInstalledError(CORE_NOT_INSTALLED_MESSAGE) from exc
        return text.rstrip() + "\n"

    def topic_output(self, topic: str) -> str:
        """Return one topic under its ``# Skill topic: <t>`` line, ``arch-qa`` followed by its checklist."""
        if topic not in TOPIC_NAMES:
            raise UnknownTopicError(UNKNOWN_TOPIC_TEMPLATE.format(topic=topic, valid=", ".join(TOPIC_NAMES)))
        try:
            body = (self.skill_dir / TOPICS_DIRNAME / f"{topic}.md").read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise NotInstalledError(TOPIC_NOT_INSTALLED_TEMPLATE.format(topic=topic)) from exc
        if topic != CHECKLIST_TOPIC:
            return f"# Skill topic: {topic}\n\n{body.strip()}\n"
        checklist = self.read_checklist().strip()
        if not checklist:
            raise NotInstalledError(CHECKLIST_NOT_INSTALLED_TEMPLATE.format(topic=topic))
        return f"# Skill topic: {topic}\n\n{body.strip()}\n\n{checklist}\n"

    def all_output(self) -> str:
        """Return the core then every topic, one empty line between parts; first missing part raises."""
        parts = [self.core_output(), *(self.topic_output(name) for name in TOPIC_NAMES)]
        return "\n".join(parts)


def build_library(read_checklist: Callable[[], str] | None = None) -> SkillLibrary:
    """Build the library on the configured skill directory and the resolved checklist reader."""
    return SkillLibrary(config.skill_dir(), read_checklist or arch_checks.read_checklist)
