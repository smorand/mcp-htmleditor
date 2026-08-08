"""Configuration for mcp-htmleditor, backed by pydantic-settings.

Every value comes from the :class:`Settings` model: environment variables
prefixed ``HTMLEDITOR_``, a local ``.env`` file, or the XDG defaults.

    bin       ~/.local/bin                          HTMLEDITOR_BIN_DIR
    templates ~/.config/mcp-htmleditor/templates    HTMLEDITOR_TEMPLATES_DIR
    logs      ~/.cache/mcp-htmleditor/logs          HTMLEDITOR_LOGS, HTMLEDITOR_LOG_DIR
    cache     ~/.cache/mcp-htmleditor               HTMLEDITOR_CACHE_DIR
    reference ~/.cache/mcp-htmleditor/reference     (generated pandoc reference.docx)
    state     next to the edited HTML file          (.mcp_state.json)

Other variables:
    HTMLEDITOR_HOST              HTTP bind address (default localhost)
    HTMLEDITOR_PORT              default HTTP port (default 7842)
    HTMLEDITOR_POLL_INTERVAL     browser polling interval in ms (default 1000)
    HTMLEDITOR_OTEL_DESTINATION  OTLP endpoint; unset means local JSONL export
    HTMLEDITOR_OTEL_API_KEY      bearer token sent to the OTLP endpoint
    XDG_CONFIG_HOME              base for config (default ~/.config)
    XDG_CACHE_HOME               base for cache  (default ~/.cache)

The module level helpers (:func:`templates_dir`, :func:`log_dir`, ...) are the
public API used across the codebase; they all delegate to :func:`get_settings`.
Settings are built once per distinct environment signature and memoized, so a
process that never changes its environment builds them exactly once.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "mcp-htmleditor"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7842
DEFAULT_POLL_INTERVAL = 1000  # ms

_INT_FALLBACKS = {"port": DEFAULT_PORT, "poll_interval": DEFAULT_POLL_INTERVAL}

# Every field holding a filesystem path override, validated the same way.
_PATH_FIELDS = (
    "templates_dir_override",
    "logs_override",
    "log_dir_override",
    "cache_dir_override",
    "bin_dir_override",
    "xdg_config_home_override",
    "xdg_cache_home_override",
)

# Environment variables that change the resolved configuration. Used only to key
# the settings memoization, never to read a value: reads go through Settings.
_SIGNIFICANT_ENV_VARS = (
    "HTMLEDITOR_HOST",
    "HTMLEDITOR_PORT",
    "HTMLEDITOR_POLL_INTERVAL",
    "HTMLEDITOR_TEMPLATES_DIR",
    "HTMLEDITOR_LOGS",
    "HTMLEDITOR_LOG_DIR",
    "HTMLEDITOR_CACHE_DIR",
    "HTMLEDITOR_BIN_DIR",
    "HTMLEDITOR_OTEL_DESTINATION",
    "HTMLEDITOR_OTEL_API_KEY",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
)


class Settings(BaseSettings):
    """Runtime settings of the editor, server and exporters.

    Fields suffixed ``_override`` hold the raw environment value; the resolved
    value (default applied, ``~`` expanded) is exposed by the matching property,
    so callers never have to know whether an override was set.
    """

    model_config = SettingsConfigDict(
        env_prefix="HTMLEDITOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Fields carrying a validation_alias (the exact environment variable name)
        # must stay constructible by their python name too, so callers and tests
        # can build a Settings without touching the environment.
        populate_by_name=True,
    )

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    poll_interval: int = DEFAULT_POLL_INTERVAL

    otel_destination: str | None = None
    otel_api_key: str | None = None

    templates_dir_override: Path | None = Field(default=None, validation_alias="HTMLEDITOR_TEMPLATES_DIR")
    logs_override: Path | None = Field(default=None, validation_alias="HTMLEDITOR_LOGS")
    log_dir_override: Path | None = Field(default=None, validation_alias="HTMLEDITOR_LOG_DIR")
    cache_dir_override: Path | None = Field(default=None, validation_alias="HTMLEDITOR_CACHE_DIR")
    bin_dir_override: Path | None = Field(default=None, validation_alias="HTMLEDITOR_BIN_DIR")
    xdg_config_home_override: Path | None = Field(default=None, validation_alias="XDG_CONFIG_HOME")
    xdg_cache_home_override: Path | None = Field(default=None, validation_alias="XDG_CACHE_HOME")

    @field_validator("port", "poll_interval", mode="before")
    @classmethod
    def _tolerate_invalid_int(cls, value: Any, info: Any) -> Any:
        """Fall back to the default when the environment holds a non-integer.

        A malformed ``HTMLEDITOR_PORT`` must not prevent the tool from starting.
        """
        if value is None or value == "":
            return _INT_FALLBACKS[str(info.field_name)]
        try:
            return int(value)
        except (TypeError, ValueError):
            return _INT_FALLBACKS[str(info.field_name)]

    @field_validator(*_PATH_FIELDS, mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        """Treat an empty or whitespace only variable as unset, not as ``.``."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(*_PATH_FIELDS, mode="after")
    @classmethod
    def _expand_path(cls, value: Path | None) -> Path | None:
        """Expand ``~`` in path overrides (uses $HOME, like the shell does)."""
        if value is None:
            return None
        return value.expanduser()

    @property
    def xdg_config_home(self) -> Path:
        """Base config directory (XDG_CONFIG_HOME or ~/.config)."""
        return self.xdg_config_home_override or Path.home() / ".config"

    @property
    def xdg_cache_home(self) -> Path:
        """Base cache directory (XDG_CACHE_HOME or ~/.cache)."""
        return self.xdg_cache_home_override or Path.home() / ".cache"

    @property
    def config_dir(self) -> Path:
        """Application config directory: ~/.config/mcp-htmleditor."""
        return self.xdg_config_home / APP_NAME

    @property
    def templates_dir(self) -> Path:
        """User templates directory."""
        return self.templates_dir_override or self.config_dir / "templates"

    @property
    def cache_dir(self) -> Path:
        """Application cache directory: ~/.cache/mcp-htmleditor."""
        return self.cache_dir_override or self.xdg_cache_home / APP_NAME

    @property
    def log_dir(self) -> Path:
        """Log directory: HTMLEDITOR_LOG_DIR, then HTMLEDITOR_LOGS, then cache/logs."""
        return self.log_dir_override or self.logs_override or self.cache_dir / "logs"

    @property
    def log_file(self) -> Path:
        """Rotating application log file."""
        return self.log_dir / f"{APP_NAME}.log"

    @property
    def otel_log_file(self) -> Path:
        """JSONL span file used when no OTLP destination is configured."""
        return self.log_dir / f"{APP_NAME}-otel.log"

    @property
    def reference_dir(self) -> Path:
        """Directory holding the generated pandoc reference.docx files."""
        return self.cache_dir / "reference"

    @property
    def bin_dir(self) -> Path:
        """Executable install target: ~/.local/bin."""
        return self.bin_dir_override or Path.home() / ".local" / "bin"


def _env_signature() -> tuple[str, ...]:
    """Return a hashable snapshot of everything that shapes the settings."""
    return (str(Path.home()), *(os.environ.get(name, "") for name in _SIGNIFICANT_ENV_VARS))


@lru_cache(maxsize=8)
def _build_settings(signature: tuple[str, ...]) -> Settings:  # noqa: ARG001 - cache key only
    """Build a Settings instance; memoized on the environment signature."""
    return Settings()


def get_settings() -> Settings:
    """Return the settings for the current environment (memoized)."""
    return _build_settings(_env_signature())


def reset_settings_cache() -> None:
    """Drop the memoized settings; used by tests and after an env change."""
    _build_settings.cache_clear()


def xdg_config_home() -> Path:
    """Base config directory (XDG_CONFIG_HOME or ~/.config)."""
    return get_settings().xdg_config_home


def xdg_cache_home() -> Path:
    """Base cache directory (XDG_CACHE_HOME or ~/.cache)."""
    return get_settings().xdg_cache_home


def config_dir() -> Path:
    """Application config directory: ~/.config/mcp-htmleditor."""
    return get_settings().config_dir


def templates_dir() -> Path:
    """User templates directory (HTMLEDITOR_TEMPLATES_DIR)."""
    return get_settings().templates_dir


def log_dir() -> Path:
    """Log directory (HTMLEDITOR_LOG_DIR or HTMLEDITOR_LOGS)."""
    return get_settings().log_dir


def cache_dir() -> Path:
    """Application cache directory (HTMLEDITOR_CACHE_DIR)."""
    return get_settings().cache_dir


def reference_dir() -> Path:
    """Directory holding the generated pandoc reference.docx files."""
    return get_settings().reference_dir


def bin_dir() -> Path:
    """Executable install target (HTMLEDITOR_BIN_DIR)."""
    return get_settings().bin_dir


def default_host() -> str:
    """Default HTTP bind address (HTMLEDITOR_HOST or localhost)."""
    return get_settings().host


def default_port() -> int:
    """Default HTTP port (HTMLEDITOR_PORT or 7842)."""
    return get_settings().port


def default_poll_interval() -> int:
    """Default polling interval in ms (HTMLEDITOR_POLL_INTERVAL or 1000)."""
    return get_settings().poll_interval
