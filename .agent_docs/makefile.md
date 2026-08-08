# Makefile targets

`make` is the single entry point. Every tool runs through `uv run`, so nothing depends
on a globally installed ruff, mypy or pytest. `make help` prints the same list.

## Dependencies

| Target | What it does |
|--------|--------------|
| `sync` | `uv sync`: create/refresh `.venv` from `uv.lock`, dev group included |

## Running

| Target | What it does |
|--------|--------------|
| `run` | `uv run mcp-htmleditor $(ARGS)`; without `ARGS` prints `--help` |
| `run-dev` | `uv run python -m mcp_htmleditor $(ARGS)`, straight from the working tree |

```bash
make run ARGS='export pptx pres.html /tmp/out.pptx'
make run-dev ARGS='-v serve doc.html'
```

## Tests

| Target | What it does |
|--------|--------------|
| `test` | `pytest -v` (accepts `ARGS='-k pptx'`) |
| `test-cov` | `pytest -v --cov=mcp_htmleditor --cov-report=term-missing`, gate 80 % |

## Quality

| Target | What it does |
|--------|--------------|
| `lint` | `ruff check .` (src, tests, tools) |
| `lint-fix` | `ruff check --fix .` |
| `format` | `ruff format .` |
| `format-check` | `ruff format --check .` |
| `typecheck` | `mypy src/`, strict |
| `security` | `bandit -q -r src/ -c pyproject.toml` |
| `check` | lint, format-check, typecheck, security, test-cov. Run before every commit |

## Build and install

| Target | What it does |
|--------|--------------|
| `build` | Writes `VERSION` into `src/mcp_htmleditor/version.py`, runs `uv build`, restores the file to `dev` |
| `install` | Injects `VERSION` the same way, installs the CLI as a uv tool, plus templates, log dir and the Pi skill, then restores the file |
| `install-skill` | Only the dynamic Pi skill |
| `uninstall` | Removes the uv tool, the templates, the log dir and the Pi skill |

`VERSION` defaults to `git describe --tags --always --dirty`, or `dev` outside a repo.
`build`, `docker-build` and `install` all write it into `version.py` before packaging and
restore the committed `dev` placeholder afterwards, so a build never leaves the working
tree dirty and `mcp-htmleditor --version` on an installed CLI shows the real tag.

### Why `install` uses a uv tool

`pip install --user .` used to leave a non editable copy in the user `site-packages`
whose console script sits earlier on `PATH`, so the installed command kept running old
code and even shadowed the sources during test runs. `uv tool install . --reinstall
--force` puts the package in its own isolated environment
(`~/.local/share/uv/tools/mcp-htmleditor/`) and links a single executable into
`BIN_DIR`. Nothing lands in the user `site-packages`, so nothing can shadow `src/`.

`install` also removes a legacy `pip --user` copy when it finds one, so upgrading from
the old layout is a single `make install`.

The tool environment is a snapshot: after changing the sources, run `make install`
again to refresh the installed CLI (development uses `make run`, `make run-dev` or
`make test`, which all read the working tree).

## Docker

| Target | What it does |
|--------|--------------|
| `docker-build` | `docker build --build-arg APP_VERSION=$(VERSION) -t $(MAKE_DOCKER_PREFIX)mcp-htmleditor:$(DOCKER_TAG) .` |
| `docker-push` | Pushes that tag |
| `docker` | `docker-build` then `docker-push` |
| `run-up` | Builds, then `docker compose up -d` |
| `run-down` | `docker compose down` |

```bash
MAKE_DOCKER_PREFIX=ghcr.io/smorand/ DOCKER_TAG=v1.0.0 make docker
```

## Project specific

| Target | What it does |
|--------|--------------|
| `bootstrap-ei` | Regenerates `templates/bootstrap/slides-ei-empty.html` from the EI reference |

## Cleanup and info

| Target | What it does |
|--------|--------------|
| `clean` | Caches, build artifacts, coverage |
| `clean-all` | `clean` plus `.venv` and `uv.lock` |
| `info` | Project name, package, version, python, install targets |
| `help` | Target list |

## Install path overrides

All of them are plain environment variables, usable as `make install VAR=...`.

| Variable | Default | Used for |
|----------|---------|----------|
| `BIN_DIR` | `~/.local/bin` | CLI executable (also `UV_TOOL_BIN_DIR`) |
| `CONFIG_DIR` | `~/.config/mcp-htmleditor` | Base of the templates dir |
| `TEMPLATES_DIR` | `$(CONFIG_DIR)/templates` | Installed templates |
| `CACHE_DIR` | `~/.cache/mcp-htmleditor` | Base of the log dir |
| `LOG_DIR` | `$(CACHE_DIR)/logs` | Log dir created by `install` |
| `PI_SKILLS_DIR` | `~/.pi/agent/dynamic-skills/html-editor` | Dynamic Pi skill |

The runtime reads the same locations through `HTMLEDITOR_*` variables
(see `README.md` and `.agent_docs/python.md`).
