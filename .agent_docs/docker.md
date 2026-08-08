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
`reference.docx` live there).

`--no-browser` matters: without it `serve` tries to open a browser inside the container.

## Compose

`docker-compose.yml` publishes 7842, mounts `./data` on `/data` and keeps the cache in a
named volume. Drop the document to edit in `./data/document.html`, or override the
command:

```yaml
command: ["serve", "--no-browser", "/data/ma-presentation.html"]
```

`docker-compose.prod.yml` is the overlay that builds locally with the version injected
and forwards the OTel variables:

```bash
APP_VERSION=$(git describe --tags --always) \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

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
