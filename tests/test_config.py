"""Tests for XDG config resolution (mcp_htmleditor.config)."""

from __future__ import annotations

from pathlib import Path

from mcp_htmleditor import config


def test_defaults_without_env(monkeypatch) -> None:
    """Without env overrides, paths follow XDG defaults under $HOME."""
    for var in [
        "HTMLEDITOR_TEMPLATES_DIR",
        "HTMLEDITOR_LOG_DIR",
        "HTMLEDITOR_BIN_DIR",
        "HTMLEDITOR_PORT",
        "HTMLEDITOR_POLL_INTERVAL",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/tester")))

    assert config.config_dir() == Path("/home/tester/.config/mcp-htmleditor")
    assert config.templates_dir() == Path("/home/tester/.config/mcp-htmleditor/templates")
    assert config.log_dir() == Path("/home/tester/.cache/mcp-htmleditor/logs")
    assert config.bin_dir() == Path("/home/tester/.local/bin")
    assert config.default_port() == 7842
    assert config.default_poll_interval() == 1000


def test_env_overrides(monkeypatch) -> None:
    """Env vars override the default paths and scalars."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", "/custom/templates")
    monkeypatch.setenv("HTMLEDITOR_LOG_DIR", "/custom/logs")
    monkeypatch.setenv("HTMLEDITOR_PORT", "9000")
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", "500")

    assert config.templates_dir() == Path("/custom/templates")
    assert config.log_dir() == Path("/custom/logs")
    assert config.default_port() == 9000
    assert config.default_poll_interval() == 500


def test_xdg_bases(monkeypatch) -> None:
    """XDG_CONFIG_HOME / XDG_CACHE_HOME shift the config and cache bases."""
    monkeypatch.delenv("HTMLEDITOR_TEMPLATES_DIR", raising=False)
    monkeypatch.delenv("HTMLEDITOR_LOG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/config")
    monkeypatch.setenv("XDG_CACHE_HOME", "/xdg/cache")

    assert config.templates_dir() == Path("/xdg/config/mcp-htmleditor/templates")
    assert config.log_dir() == Path("/xdg/cache/mcp-htmleditor/logs")


def test_invalid_port_falls_back(monkeypatch) -> None:
    """A non-integer port env value falls back to the default."""
    monkeypatch.setenv("HTMLEDITOR_PORT", "not-a-number")
    assert config.default_port() == 7842
