"""Tests for logging setup (mcp_htmleditor.logging_config)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from rich.logging import RichHandler

from mcp_htmleditor.config import Settings
from mcp_htmleditor.logging_config import (
    CONSOLE_HANDLER_NAME,
    FILE_HANDLER_NAME,
    resolve_level,
    setup_logging,
)


@pytest.fixture
def bare_root() -> Iterator[logging.Logger]:
    """Give each test an empty root logger and restore it afterwards."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    root.handlers = []
    yield root
    for handler in root.handlers:
        handler.close()
    root.handlers = saved_handlers
    root.setLevel(saved_level)


def _settings(log_dir: Path) -> Settings:
    """Return settings whose log directory is the given path."""
    return Settings(log_dir_override=log_dir)


def test_resolve_level_maps_flags() -> None:
    """-q wins over -v; a single -v is already DEBUG."""
    assert resolve_level() == logging.INFO
    assert resolve_level(1) == logging.DEBUG
    assert resolve_level(5) == logging.DEBUG
    assert resolve_level(0, is_quiet=True) == logging.ERROR
    assert resolve_level(3, is_quiet=True) == logging.ERROR


def test_setup_logging_installs_both_handlers(bare_root: logging.Logger, tmp_path: Path) -> None:
    """A console handler on stderr plus a rotating file handler are installed."""
    log_file = setup_logging(settings=_settings(tmp_path))

    names = {handler.name for handler in bare_root.handlers}
    assert {CONSOLE_HANDLER_NAME, FILE_HANDLER_NAME} <= names
    assert log_file == tmp_path / "mcp-htmleditor.log"
    assert log_file.exists()


def test_console_handler_never_omits_timestamps(bare_root: logging.Logger, tmp_path: Path) -> None:
    """Every console line must carry its own timestamp."""
    setup_logging(settings=_settings(tmp_path))

    console = next(h for h in bare_root.handlers if h.name == CONSOLE_HANDLER_NAME)
    assert isinstance(console, RichHandler)
    assert console._log_render.omit_repeated_times is False
    assert console.console.stderr is True


def test_two_consecutive_console_lines_both_show_a_timestamp(
    bare_root: logging.Logger,
    tmp_path: Path,
) -> None:
    """A timestamp must never be inferred from the previous line."""
    setup_logging(settings=_settings(tmp_path))
    console = next(h for h in bare_root.handlers if h.name == CONSOLE_HANDLER_NAME)
    assert isinstance(console, RichHandler)
    console.console = Console(file=StringIO(), width=200, force_terminal=False)

    logging.getLogger("mcp_htmleditor.test").warning("first")
    logging.getLogger("mcp_htmleditor.test").warning("second")

    rendered = console.console.file.getvalue().splitlines()
    stamped = [line for line in rendered if re.match(r"^\[?\d\d", line)]
    assert len(stamped) == 2


def test_setup_logging_writes_to_the_log_file(bare_root: logging.Logger, tmp_path: Path) -> None:
    """A log record reaches the file handler with its timestamp and logger name."""
    log_file = setup_logging(verbosity=1, settings=_settings(tmp_path))
    logging.getLogger("mcp_htmleditor.test").debug("hello %s", "file")

    assert log_file is not None
    content = log_file.read_text(encoding="utf-8")
    assert "hello file" in content
    assert "mcp_htmleditor.test" in content
    assert "DEBUG" in content


def test_setup_logging_is_idempotent(bare_root: logging.Logger, tmp_path: Path) -> None:
    """Calling setup twice does not duplicate handlers, it re-applies the level."""
    setup_logging(settings=_settings(tmp_path))
    setup_logging(verbosity=1, settings=_settings(tmp_path))

    ours = [h for h in bare_root.handlers if h.name in {CONSOLE_HANDLER_NAME, FILE_HANDLER_NAME}]
    assert len(ours) == 2
    assert bare_root.level == logging.DEBUG


def test_noisy_third_party_loggers_stay_at_info(bare_root: logging.Logger, tmp_path: Path) -> None:
    """PIL must not dump every PNG chunk when we ask for DEBUG."""
    setup_logging(verbosity=1, settings=_settings(tmp_path))

    assert logging.getLogger("PIL").level == logging.INFO


def test_unwritable_log_dir_keeps_the_console(bare_root: logging.Logger, tmp_path: Path) -> None:
    """An unusable log directory degrades to console-only logging."""
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")

    log_file = setup_logging(settings=_settings(blocker))

    names = {handler.name for handler in bare_root.handlers}
    assert log_file is None
    assert CONSOLE_HANDLER_NAME in names
    assert FILE_HANDLER_NAME not in names
