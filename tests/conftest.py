"""Shared pytest fixtures for mcp-htmleditor tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from mcp_htmleditor import config as config_module
from mcp_htmleditor import state as state_module


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    """Drop the memoized Settings around each test.

    Settings are memoized on an environment signature, so a test that sets
    HTMLEDITOR_* variables must not hand its instance over to the next one.
    """
    config_module.reset_settings_cache()
    yield
    config_module.reset_settings_cache()


@pytest.fixture
def reset_state() -> Iterator[None]:
    """Reset the EditorState singleton around each test.

    EditorState is a process-wide singleton keyed on a class attribute.
    Tests must start from a clean instance so state does not leak between
    cases.
    """
    state_module.EditorState._instance = None
    state_module.EditorState._initialized = False
    yield
    state_module.EditorState._instance = None
    state_module.EditorState._initialized = False


@pytest.fixture
def fresh_state(reset_state: None) -> state_module.EditorState:
    """Return a freshly initialized EditorState singleton."""
    return state_module.get_state()


@pytest.fixture
def html_file(tmp_path: Path) -> Path:
    """Write a minimal HTML file into tmp_path and return its path."""
    path = tmp_path / "doc.html"
    path.write_text(
        "<!DOCTYPE html>\n<html><head><title>t</title></head><body><p>hello</p></body></html>",
        encoding="utf-8",
    )
    return path
