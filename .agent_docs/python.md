# Python standards for mcp-htmleditor

Reference: the personal `python` skill (2025-2026 standards). This file records how
they apply here and every deliberate deviation, with its reason.

## Toolchain

| Concern | Tool | Entry point |
|---------|------|-------------|
| Dependencies, venv, lock | `uv` (never `pip`) | `make sync` |
| Lint + format | `ruff` | `make lint`, `make format` |
| Types | `mypy` strict | `make typecheck` |
| Security | `bandit` | `make security` |
| Tests + coverage | `pytest`, `pytest-cov` | `make test`, `make test-cov` |

`make` is the only supported interface. Never call `uv run pytest` or `ruff` by hand:
the targets carry the flags the gate expects (see `.agent_docs/makefile.md`).

`uv.lock` is committed. `requires-python = ">=3.13"`. Build backend: hatchling, with
`templates/` and `skill/` force-included into the wheel so an installed copy ships them.

## Layout

`src/mcp_htmleditor/` is a real package (layout B), so `pyproject.toml` declares
`sources = ["src"]` and the console script is `mcp_htmleditor.cli:main`.
`pythonpath = ["src"]` in `[tool.pytest.ini_options]` is critical: without it a
previously installed non editable copy shadows the working tree and the suite
measures the wrong code.

```
src/mcp_htmleditor/
  __init__.py         re-exports __version__ only
  __main__.py         `python -m mcp_htmleditor` (make run-dev)
  version.py          __version__ = "dev", overwritten at build time
  config.py           Settings (pydantic-settings) + module level accessors
  logging_config.py   setup_logging(): rich console on stderr + rotating file
  tracing.py          configure_tracing(), trace_span(), JSONL span exporter
  cli.py              click group, -v/-q, --version, subcommands
  ...                 (see .agent_docs/architecture.md)
```

## Configuration

Everything goes through `Settings(BaseSettings)` with `env_prefix="HTMLEDITOR_"` and
`.env` support. Direct `os.environ` reads are forbidden, with one documented exception:
`config._env_signature()` snapshots the variable names to key the settings memoization,
it never reads a value for its meaning.

Fields suffixed `_override` carry the raw variable (`validation_alias` pins the exact
name, which also lets `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` bypass the prefix); the
resolved value is a property. `populate_by_name=True` keeps `Settings(log_dir_override=...)`
usable from code and tests.

Two validators encode the tolerance the CLI needs:

* a malformed `HTMLEDITOR_PORT` or `HTMLEDITOR_POLL_INTERVAL` falls back to the default
  instead of aborting the process;
* an empty or blank path variable means unset, not `Path(".")`.

The module level helpers (`templates_dir()`, `log_dir()`, `cache_dir()`,
`reference_dir()`, `default_port()`, `default_poll_interval()`, `bin_dir()`,
`default_host()`) are the public API used across the codebase and delegate to
`get_settings()`. Settings are memoized per environment signature, so a process that
does not touch its environment builds them once. `reset_settings_cache()` exists for
tests and is called by an autouse fixture in `tests/conftest.py`.

## Logging

`setup_logging(verbosity, is_quiet, settings)` is called once, from the click group.

* Console handler: `RichHandler` on **stderr**, `omit_repeated_times=False`. stdout is
  reserved for the MCP stdio protocol and for `click.echo` user output; a log line on
  stdout would corrupt both. The flag is mandatory: every line shows its own timestamp.
* File handler: `RotatingFileHandler` in the resolved log dir, 2 MB, 3 backups.
* `PIL`, `urllib3`, `httpx`, `httpcore`, `asyncio` and `opentelemetry` are pinned to INFO
  even under `-v`, otherwise PIL dumps every PNG chunk of every exported image.

Rules in code: one `logger = logging.getLogger(__name__)` per module, `%` style lazy
formatting, never an f-string in a log call, `click.echo` for user output only.

## Tracing

`configure_tracing()` installs a `TracerProvider` and is memoized on its destination.
`trace_span(name, attributes)` is a context manager that records exceptions and works
as a no-op when no provider is installed, so instrumented code stays cheap.

Span names use `category.operation`; see `.agent_docs/observability.md` for the current
inventory and the attribute rules (never document content, prompts or credentials).

## Version

`src/mcp_htmleditor/version.py` holds `"dev"` in the working tree and is committed.
`make build`, `make docker-build` and `make install` overwrite it from
`git describe --tags --always --dirty`, then restore the `dev` placeholder, so the
working tree never ends up dirty.
The version is exposed by `mcp-htmleditor --version` and by `GET /health`.

## Deliberate deviations from the skill defaults

| Rule | Decision | Reason |
|------|----------|--------|
| Async first (`asyncio`, `httpx`, `aiofiles`) | Kept synchronous: `http.server`, `subprocess.run` | Single user editor, one browser, one pandoc call. An async rewrite would add a loop, cancellation handling and no measurable gain. `asyncio_mode = "auto"` is configured so an async test would just work. |
| CLI with Typer | `click` | The CLI predates the rule and click is a fastmcp dependency already. Feature parity, one less dependency. |
| `Any` forbidden in signatures | `ANN401` disabled | python-pptx and bs4 hand back untyped objects; `Any` is the honest annotation there and mypy strict still governs everything else. |
| mypy strict everywhere | `follow_imports = "skip"` for `pptx.*` | python-pptx ships `py.typed` yet leaves `RGBColor.from_string`, `Inches` and friends unannotated, so strict mode would reject every call into the library. |
| No blanket bandit skips | `B404`, `B603`, `B607`, `B314`, `B405`, `B406` skipped in `[tool.bandit]` | The only subprocess is pandoc, resolved from PATH by design, always a fixed argument list, never a shell, never interpolating document content. The only XML parsed is `word/*.xml` from a DOCX pandoc just produced locally. The rationale lives in one reviewable place instead of scattered `# nosec`. |
| Coverage 80 % | Gate 80 %, actual about 95 % | `cli.py`, `mcp_server.py` and `__main__.py` are thin wrappers and are omitted; the `_EditorHandler` network class is `# pragma: no cover`. |

## Post change checklist

1. `make check` green (lint, format-check, typecheck, security, test-cov).
2. New settings read through `Settings`, never `os.environ`.
3. New external call traced (`category.operation`) and logged with `%` formatting.
4. New behaviour covered by a test; exports validated on the regression set
   (`.agent_docs/testing.md`).
5. `AGENTS.md`, `README.md` and the relevant `.agent_docs/*.md` updated.
