"""Logging setup for mcp-htmleditor.

Two handlers are installed on the root logger:

* a :class:`rich.logging.RichHandler` on **stderr**. stdout carries the MCP
  stdio protocol and the CLI user output, so a log line on stdout would corrupt
  both. ``omit_repeated_times=False`` is mandatory: every console line shows its
  own timestamp, a timestamp is never inferred from the previous line.
* a rotating file handler under the resolved log directory
  (``~/.cache/mcp-htmleditor/logs/mcp-htmleditor.log`` by default, moved with
  ``HTMLEDITOR_LOG_DIR`` or ``HTMLEDITOR_LOGS``).

:func:`setup_logging` is idempotent: calling it twice does not duplicate
handlers, it only re-applies the level.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .config import APP_NAME, Settings, get_settings

CONSOLE_HANDLER_NAME = "mcp-htmleditor-console"
FILE_HANDLER_NAME = "mcp-htmleditor-file"

FILE_MAX_BYTES = 2_000_000
FILE_BACKUP_COUNT = 3

_FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
_LEVELS = (logging.INFO, logging.DEBUG)

# Third party loggers whose DEBUG output drowns ours (PIL dumps every PNG chunk).
_NOISY_LOGGERS = ("PIL", "urllib3", "asyncio", "httpx", "httpcore", "opentelemetry")

logger = logging.getLogger(__name__)


def resolve_level(verbosity: int = 0, is_quiet: bool = False) -> int:
    """Return the log level for the CLI verbosity flags.

    Args:
        verbosity: Number of ``-v`` flags (0 means INFO, 1 or more means DEBUG).
        is_quiet: True when ``-q`` was passed; wins over ``-v``.

    Returns:
        A :mod:`logging` level.
    """
    if is_quiet:
        return logging.ERROR
    return _LEVELS[min(max(verbosity, 0), len(_LEVELS) - 1)]


def setup_logging(verbosity: int = 0, is_quiet: bool = False, settings: Settings | None = None) -> Path | None:
    """Install the console and file handlers on the root logger.

    Args:
        verbosity: Number of ``-v`` flags passed on the command line.
        is_quiet: True when ``-q`` was passed.
        settings: Injected settings; resolved from the environment when omitted.

    Returns:
        The log file in use, or None when the log directory is not writable
        (the console handler is still installed in that case).
    """
    resolved = settings if settings is not None else get_settings()
    level = resolve_level(verbosity, is_quiet)

    root = logging.getLogger()
    root.setLevel(level)

    existing = {handler.name for handler in root.handlers}
    if CONSOLE_HANDLER_NAME not in existing:
        root.addHandler(_build_console_handler())
    if FILE_HANDLER_NAME in existing:
        log_file: Path | None = resolved.log_file
    else:
        log_file = _install_file_handler(root, resolved.log_file)

    for handler in root.handlers:
        if handler.name in {CONSOLE_HANDLER_NAME, FILE_HANDLER_NAME}:
            handler.setLevel(level)

    logging.getLogger(APP_NAME).setLevel(level)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(level, logging.INFO))
    return log_file


def _build_console_handler() -> logging.Handler:
    """Return the stderr rich handler, one timestamp per line."""
    handler = RichHandler(
        console=Console(stderr=True),
        omit_repeated_times=False,
        rich_tracebacks=True,
        show_path=False,
        markup=False,
    )
    handler.set_name(CONSOLE_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def _install_file_handler(root: logging.Logger, log_file: Path) -> Path | None:
    """Attach the rotating file handler, or return None when unavailable."""
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file,
            maxBytes=FILE_MAX_BYTES,
            backupCount=FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Log file unavailable (%s): %s", log_file, exc)
        return None
    handler.set_name(FILE_HANDLER_NAME)
    handler.setFormatter(logging.Formatter(_FILE_FORMAT))
    root.addHandler(handler)
    return log_file
