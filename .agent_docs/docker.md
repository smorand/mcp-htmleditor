# Docker

```bash
make docker-build     # image mcp-htmleditor:latest, APP_VERSION from git
make run-up           # build + docker compose up -d
make run-down         # docker compose down
MAKE_DOCKER_PREFIX=ghcr.io/smorand/ DOCKER_TAG=v1.0.0 make docker   # build + push
```

## Image

Multi stage, `python:3.13-slim`.

* Builder: `uv sync --frozen --no-dev --no-editable` from the committed `uv.lock`, so the
  image is reproducible. `ARG APP_VERSION` is written into
  `src/mcp_htmleditor/version.py` before the sync, exactly like `make build` does.
* Runtime: the venv, `templates/` and `skill/` are copied over, `pandoc` is installed
  (the DOCX export needs it), and the process runs as the non root user `appuser`
  (uid 10001).
* `ENTRYPOINT ["mcp-htmleditor"]`, default `CMD ["serve", "--no-browser", "/data/document.html"]`.
* `HEALTHCHECK` polls `GET /health`, which answers `{"status": "ok", "version": ...}`.

Baked environment: `HTMLEDITOR_HOST=0.0.0.0` (a container that binds localhost would
never answer on the published port), `HTMLEDITOR_PORT=7842`,
`HTMLEDITOR_TEMPLATES_DIR=/app/templates`,
`HTMLEDITOR_CACHE_DIR=/var/cache/mcp-htmleditor` (logs, JSONL spans and the generated
`reference.docx` live there), `HTMLEDITOR_STATE_DIR=/var/lib/mcp-htmleditor` (file history and
server records; the image has no home directory, so without it every save answers 500).

`--no-browser` matters: without it `serve` tries to open a browser inside the container.

## Compose

`docker-compose.yml` publishes 7842, mounts `./data` on `/data` and keeps the cache and the state
directory (`htmleditor-state`) in named volumes. Drop the document to edit in `./data/document.html`, or override the
command:

```yaml
command: ["serve", "--no-browser", "/data/ma-presentation.html"]
```

`docker-compose.prod.yml` is the standalone file of the owner's VPS convention (web library mode, SPEC-0025): service
`mcp-htmleditor`, `command: ["webserve"]`, `expose: 7842` (no published port), network `proxy-network` (external), data
`/app/data/mcp-htmleditor` on `/data`, `env_file: /app/data/mcp-htmleditor/.env` (copied once from
`environments/prod/.env.example`), json-file logs, build arg `APP_VERSION`. It no longer extends `docker-compose.yml`; the
local stack stays `docker-compose.yml` (`make run-up`). `make deploy-vps TAG=vX.Y.Z` deploys it (`.agent_docs/makefile.md`).

The Dockerfile copies `library-seed/` into the builder stage (the wheel force-includes it as `mcp_htmleditor/library_seed`,
so the first start of an empty library creates the initial content); no Chromium is added (the library PPTX is the flow
output); `.dockerignore` drops `.git`, `.env*`, `sdlc/`, `tests/`, `docs/`, `data/` and keeps `src/`, `templates/`, `skill/`,
`library-seed/`, `pyproject.toml`, `uv.lock` and `README.md`. Checked by `tests/test_library_deploy.py` (static, nothing runs).
`webserve` in the image: `docker run -d -p 7842:7842 -e HTMLEDITOR_HOST=0.0.0.0 -e HTMLEDITOR_LIBRARY_DIR=/data/library
mcp-htmleditor:latest webserve`, then `curl -s -H 'Host: slides.scm-platform.org' http://127.0.0.1:7842/health`.

## Checks worth running after touching the image

```bash
docker run --rm mcp-htmleditor:latest --version          # version injected
docker run --rm mcp-htmleditor:latest templates          # bundled templates found
docker run -d --name ht -p 7999:7842 -v "$PWD/data:/data" mcp-htmleditor:latest
curl -s localhost:7999/health && docker inspect --format '{{.State.Health.Status}}' ht
docker rm -f ht
```

On macOS, Docker Desktop does not share `/tmp` by default: mount a directory under your
home, otherwise `/data` shows up empty and `serve` reports a missing file.

## What the container does not do

The MCP transport is stdio, so `mcp-htmleditor mcp` is meant to be spawned by the agent
runtime, not to be published by the container. The image serves the editor and runs the
exports.
