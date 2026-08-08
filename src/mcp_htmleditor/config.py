"""XDG-compliant configuration for mcp-htmleditor.

All paths are overridable via environment variables. Defaults follow the
XDG Base Directory specification:

    bin       ~/.local/bin                         (install target, informational)
    templates ~/.config/mcp-htmleditor/templates   HTMLEDITOR_TEMPLATES_DIR
    logs      ~/.cache/mcp-htmleditor/logs          HTMLEDITOR_LOG_DIR
    cache     ~/.cache/mcp-htmleditor               HTMLEDITOR_CACHE_DIR
    reference ~/.cache/mcp-htmleditor/reference     (generated pandoc reference.docx)
    state     next to the edited HTML file          (.mcp_state.json)

Other env vars:
    HTMLEDITOR_POLL_INTERVAL   browser polling interval in ms (default 1000)
    HTMLEDITOR_PORT            default HTTP port (default 7842)
    XDG_CONFIG_HOME            base for config   (default ~/.config)
    XDG_CACHE_HOME             base for cache    (default ~/.cache)
    XDG_DATA_HOME              base for data/bin (default ~/.local/share)
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "mcp-htmleditor"

DEFAULT_PORT = 7842
DEFAULT_POLL_INTERVAL = 1000  # ms


def _env_path(var: str, default: Path) -> Path:
    """Return an env-var path override, expanded, or the default."""
    value = os.environ.get(var)
    if value:
        return Path(value).expanduser()
    return default


def xdg_config_home() -> Path:
    """Base config directory (XDG_CONFIG_HOME or ~/.config)."""
    return _env_path("XDG_CONFIG_HOME", Path.home() / ".config")


def xdg_cache_home() -> Path:
    """Base cache directory (XDG_CACHE_HOME or ~/.cache)."""
    return _env_path("XDG_CACHE_HOME", Path.home() / ".cache")


def config_dir() -> Path:
    """Application config directory: ~/.config/mcp-htmleditor."""
    return xdg_config_home() / APP_NAME


def templates_dir() -> Path:
    """User templates directory.

    Override with HTMLEDITOR_TEMPLATES_DIR; default
    ~/.config/mcp-htmleditor/templates.
    """
    return _env_path("HTMLEDITOR_TEMPLATES_DIR", config_dir() / "templates")


def log_dir() -> Path:
    """Log directory.

    Override with HTMLEDITOR_LOG_DIR; default
    ~/.cache/mcp-htmleditor/logs.
    """
    return _env_path("HTMLEDITOR_LOG_DIR", xdg_cache_home() / APP_NAME / "logs")


def cache_dir() -> Path:
    """Application cache directory.

    Override with HTMLEDITOR_CACHE_DIR; default ~/.cache/mcp-htmleditor.
    """
    return _env_path("HTMLEDITOR_CACHE_DIR", xdg_cache_home() / APP_NAME)


def reference_dir() -> Path:
    """Directory holding the generated pandoc reference.docx files.

    Default ~/.cache/mcp-htmleditor/reference (follows HTMLEDITOR_CACHE_DIR).
    """
    return cache_dir() / "reference"


def bin_dir() -> Path:
    """Executable install target: ~/.local/bin (override HTMLEDITOR_BIN_DIR)."""
    return _env_path("HTMLEDITOR_BIN_DIR", Path.home() / ".local" / "bin")


def default_port() -> int:
    """Default HTTP port (HTMLEDITOR_PORT or 7842)."""
    try:
        return int(os.environ.get("HTMLEDITOR_PORT", str(DEFAULT_PORT)))
    except ValueError:
        return DEFAULT_PORT


def default_poll_interval() -> int:
    """Default polling interval in ms (HTMLEDITOR_POLL_INTERVAL or 1000)."""
    try:
        return int(os.environ.get("HTMLEDITOR_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
    except ValueError:
        return DEFAULT_POLL_INTERVAL
