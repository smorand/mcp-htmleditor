"""Tests for the pydantic-settings model behind mcp_htmleditor.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_htmleditor import config
from mcp_htmleditor.config import Settings


@pytest.fixture
def clean_env(monkeypatch) -> None:
    """Remove every variable the settings react to."""
    for name in config._SIGNIFICANT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/tester")))
    config.reset_settings_cache()


def test_settings_defaults(clean_env: None) -> None:
    """Without any override every path follows the XDG layout."""
    settings = config.get_settings()

    assert settings.host == "localhost"
    assert settings.port == 7842
    assert settings.poll_interval == 1000
    assert settings.otel_destination is None
    assert settings.otel_api_key is None
    assert settings.config_dir == Path("/home/tester/.config/mcp-htmleditor")
    assert settings.templates_dir == Path("/home/tester/.config/mcp-htmleditor/templates")
    assert settings.cache_dir == Path("/home/tester/.cache/mcp-htmleditor")
    assert settings.log_dir == Path("/home/tester/.cache/mcp-htmleditor/logs")
    assert settings.log_file == settings.log_dir / "mcp-htmleditor.log"
    assert settings.otel_log_file == settings.log_dir / "mcp-htmleditor-otel.log"
    assert settings.reference_dir == Path("/home/tester/.cache/mcp-htmleditor/reference")
    assert settings.bin_dir == Path("/home/tester/.local/bin")


def test_settings_are_memoized_per_environment(clean_env: None, monkeypatch) -> None:
    """The same environment yields the same instance; a change yields a new one."""
    first = config.get_settings()
    assert config.get_settings() is first

    monkeypatch.setenv("HTMLEDITOR_PORT", "9100")
    second = config.get_settings()

    assert second is not first
    assert second.port == 9100


def test_log_dir_override_wins_over_logs_alias(clean_env: None, monkeypatch) -> None:
    """HTMLEDITOR_LOG_DIR takes precedence over the HTMLEDITOR_LOGS alias."""
    monkeypatch.setenv("HTMLEDITOR_LOGS", "/alias/logs")
    config.reset_settings_cache()
    assert config.log_dir() == Path("/alias/logs")

    monkeypatch.setenv("HTMLEDITOR_LOG_DIR", "/explicit/logs")
    config.reset_settings_cache()
    assert config.log_dir() == Path("/explicit/logs")


def test_tilde_is_expanded_in_path_overrides(clean_env: None, monkeypatch) -> None:
    """A ``~`` in an override is expanded, an empty value means unset."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", "~/custom/templates")
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", "")
    config.reset_settings_cache()

    # expanduser reads $HOME, not the patched Path.home
    assert config.templates_dir() == Path("~/custom/templates").expanduser()
    assert config.cache_dir() == Path("/home/tester/.cache/mcp-htmleditor")


def test_cache_dir_override_moves_reference_dir(clean_env: None, monkeypatch) -> None:
    """The reference.docx cache follows HTMLEDITOR_CACHE_DIR."""
    monkeypatch.setenv("HTMLEDITOR_CACHE_DIR", "/custom/cache")
    config.reset_settings_cache()

    assert config.cache_dir() == Path("/custom/cache")
    assert config.reference_dir() == Path("/custom/cache/reference")
    assert config.log_dir() == Path("/custom/cache/logs")


def test_invalid_poll_interval_falls_back(clean_env: None, monkeypatch) -> None:
    """A non-integer polling interval falls back to the default."""
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", "soon")
    config.reset_settings_cache()

    assert config.default_poll_interval() == 1000


def test_empty_port_falls_back(clean_env: None, monkeypatch) -> None:
    """An empty HTMLEDITOR_PORT falls back to the default."""
    monkeypatch.setenv("HTMLEDITOR_PORT", "")
    config.reset_settings_cache()

    assert config.default_port() == 7842


def test_otel_settings_are_read(clean_env: None, monkeypatch) -> None:
    """The OTel endpoint and key are exposed as plain optional strings."""
    monkeypatch.setenv("HTMLEDITOR_OTEL_DESTINATION", "http://collector:4318/v1/traces")
    monkeypatch.setenv("HTMLEDITOR_OTEL_API_KEY", "secret-token")
    config.reset_settings_cache()
    settings = config.get_settings()

    assert settings.otel_destination == "http://collector:4318/v1/traces"
    assert settings.otel_api_key == "secret-token"


def test_host_override(clean_env: None, monkeypatch) -> None:
    """HTMLEDITOR_HOST changes the default bind address."""
    monkeypatch.setenv("HTMLEDITOR_HOST", "0.0.0.0")
    config.reset_settings_cache()

    assert config.default_host() == "0.0.0.0"


def test_unknown_prefixed_variable_is_ignored(clean_env: None, monkeypatch) -> None:
    """An unrelated HTMLEDITOR_* variable does not break instantiation."""
    monkeypatch.setenv("HTMLEDITOR_SOMETHING_ELSE", "1")
    config.reset_settings_cache()

    assert Settings().port == 7842


def test_xdg_bases_shift_every_directory(clean_env: None, monkeypatch) -> None:
    """XDG_CONFIG_HOME and XDG_CACHE_HOME move the whole layout."""
    monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/config")
    monkeypatch.setenv("XDG_CACHE_HOME", "/xdg/cache")
    config.reset_settings_cache()

    assert config.xdg_config_home() == Path("/xdg/config")
    assert config.xdg_cache_home() == Path("/xdg/cache")
    assert config.config_dir() == Path("/xdg/config/mcp-htmleditor")
    assert config.log_dir() == Path("/xdg/cache/mcp-htmleditor/logs")
