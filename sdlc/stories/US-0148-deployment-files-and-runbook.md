# US-0148: Deployment files and the VPS runbook

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0147, US-0146
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

Make the mode deployable on the owner's VPS: the compose file of the convention, the environment example, the Makefile deploy targets, a `.dockerignore`, the seed in the image, and a runbook that lists the Google console prerequisite and the second host name route.

## Requirements covered

- SPEC-0025/FR-NEW-057 (partial: the library answers at `slides.scm-platform.org` through nginx and TLS, plain http is redirected, the content host route exists): The web library mode SHALL be reached at the address slides.scm-platform.org through a secure connection.
  - Business rules: The address is imposed by the owner (Section 3.3).
- SPEC-0025/FR-NEW-062 (partial: folders, presentations, history, members, activity and sessions survive a redeploy because `/data` is a host directory): The web library mode SHALL keep every folder, presentation, history, member, activity line and signed in session after the product is restarted.
  - Business rules: A person signed in before a restart is still signed in after it, for the rest of the 30 days counted from their sign in.

## Independent Test

Run `make check`; on a machine with a container engine run `make docker-build` and start the image with `command: ["webserve"]`, `HTMLEDITOR_LIBRARY_DIR=/data/library` and a mounted credentials file, then `curl -s -H 'Host: slides.scm-platform.org' http://127.0.0.1:7842/health` returns `{"ok": true, ...}` and `docker inspect` shows `Health.Status` `healthy`. The assertion that is not a mock: a test parses `docker-compose.prod.yml` and fails unless `expose` has `7842`, there is no `ports` key, the network `proxy-network` is external, `env_file` is `/app/data/mcp-htmleditor/.env` and `command` is `["webserve"]`.

## Design excerpt

### Decisions

- DEC-046 (SPEC-0025): Deployment follows the owner's VPS convention: `docker-compose.prod.yml` becomes the standalone file (service `mcp-htmleditor`, `container_name: mcp-htmleditor`, `expose: ["7842"]`, `command: ["webserve"]`, `env_file: /app/data/mcp-htmleditor/.env`, volume `/app/data/mcp-htmleditor:/data`, network `proxy-network` external, build arg `APP_VERSION`, json-file logs); `environments/prod/.env.example` documents the variables (the operator copies it once to `/app/data/mcp-htmleditor/.env`, because `vps-deploy.sh` copies `environments/<env>/*` and a glob skips dotfiles) (`HTMLEDITOR_HOST=0.0.0.0`, the origins, `HTMLEDITOR_LIBRARY_DIR=/data/library`, `HTMLEDITOR_STATE_DIR=/data/state`, `HTMLEDITOR_GOOGLE_CREDENTIALS_FILE=/data/google-oauth.json`); `make deploy-vps TAG=vX.Y.Z` follows the sibling projects and adds two idempotent steps (the content host route `proxy.sh add slides-content.scm-platform.org 7842 mcp-htmleditor` with its certificate, and `chown -R 10001:10001 /app/data/mcp-htmleditor`). Obliged by: SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-058, SPEC-0025/FR-NEW-062.
- DEC-047 (SPEC-0025): The image runs `webserve` through compose (`command`), keeps `ENTRYPOINT ["mcp-htmleditor"]`, the uid 10001 user, the exec form and the `/health` `HEALTHCHECK`; the builder stage adds `COPY library-seed/ ./library-seed/` before `uv sync` (the wheel force-includes it); no Chromium is added; a `.dockerignore` is added. Obliged by: SPEC-0025/FR-NEW-054, SPEC-0025/FR-NEW-062.
- DEC-050 (SPEC-0025): Documentation: `.agent_docs/library.md` (new, the module map, flows, cookies, seams, gotchas), `AGENTS.md` (commands and index line), `README.md` (a "Web library mode" section and the VPS runbook), `.agent_docs/architecture.md` and `.agent_docs/testing.md` (pointers, counts), `.agent_docs/docker.md` (the new compose file), `.agent_docs/observability.md` (the new spans), `.agent_docs/html-conventions.md` (the editor seam); the skill `topics/editor.md` gets one paragraph (the editor in the web mode), `skill-audit` stays green. Obliged by: SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-062 (operability), AGENTS.md documentation pattern.

### Data model

No change.

### Contracts

**`docker-compose.prod.yml`** (replaces the overlay of `docker-compose.prod.yml:1-17`, DEC-046):

```yaml
services:
  mcp-htmleditor:
    build:
      context: .
      args:
        APP_VERSION: ${APP_VERSION:-dev}
    container_name: mcp-htmleditor
    command: ["webserve"]
    restart: unless-stopped
    expose:
      - "7842"
    volumes:
      - /app/data/mcp-htmleditor:/data
    env_file:
      - /app/data/mcp-htmleditor/.env
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
    networks:
      - proxy-network

networks:
  proxy-network:
    external: true
```

**`environments/prod/.env.example`** (non secret, copied by the operator once to `/app/data/mcp-htmleditor/.env`): `HTMLEDITOR_HOST=0.0.0.0`, `HTMLEDITOR_PORT=7842`, `HTMLEDITOR_LIBRARY_ORIGIN=https://slides.scm-platform.org`, `HTMLEDITOR_LIBRARY_CONTENT_ORIGIN=https://slides-content.scm-platform.org`, `HTMLEDITOR_LIBRARY_DIR=/data/library`, `HTMLEDITOR_STATE_DIR=/data/state`, `HTMLEDITOR_GOOGLE_CREDENTIALS_FILE=/data/google-oauth.json`, commented `HTMLEDITOR_OTEL_DESTINATION`, `HTMLEDITOR_OTEL_API_KEY`.

**Dockerfile**: add `COPY library-seed/ ./library-seed/` after `COPY skill/ ./skill/` (builder stage, `Dockerfile:19`); nothing else changes (non root uid 10001, exec form, `HEALTHCHECK` on `/health`). **`.dockerignore`** (new): `.git`, `.gitignore`, `**/.DS_Store`, `.env`, `.env.*`, `.venv`, `**/__pycache__`, `**/*.pyc`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `coverage/`, `*.log`, `sdlc/`, `tests/`, `docs/`, `*.pptx`, `data/`; `templates/`, `skill/`, `src/`, `library-seed/`, `pyproject.toml`, `uv.lock` and `README.md` must stay in the context.

**Makefile** (variables overridable, defaults as the sibling projects): `VPS_HOST ?= vps`, `VPS_APP_NAME ?= mcp-htmleditor`, `VPS_ENDPOINT ?= slides.scm-platform.org:7842`, `VPS_CONTENT_HOST ?= slides-content.scm-platform.org`, `VPS_GIT_ORG ?= smorand`, `VPS_GIT_REPO ?= mcp-htmleditor`, `VPS_MANAGEMENT_DIR ?= /app/vps-management`; targets `deploy-vps` (requires `TAG`; `git tag -f` and push, then over `ssh $(VPS_HOST)`: `vps-undeploy.sh`, `vps-deploy.sh $(VPS_GIT_ORG)/$(VPS_GIT_REPO)@$(TAG) prod $(VPS_ENDPOINT) ./environments`, `proxy.sh add $(VPS_CONTENT_HOST) 7842 $(VPS_APP_NAME)` unless already listed, `chown -R 10001:10001 /app/data/$(VPS_APP_NAME)`, then `docker compose -f docker-compose.prod.yml build --no-cache` and `up -d` in `/app/services/$(VPS_APP_NAME)`) and `undeploy-vps` (keeps data); both added to `.PHONY` and `make help`. The certificate of the content host is obtained once with `letsencrypt.sh obtain` (runbook), not by the target.

**Runbook** (`README.md`, section "Deploying the web library mode"), in this order: (1) Google console: add the authorized redirect URI `https://slides.scm-platform.org/auth/callback` to the OAuth client of the project that owns `~/.credentials/scm-pwd-web.json` (every sign in ends with `Sign-in is unavailable. Try again later.` until done); (2) DNS: `*.scm-platform.org` already resolves to `31.97.54.67`, verify with `dig +short slides.scm-platform.org slides-content.scm-platform.org`; (3) certificates: `ssh vps "cd /app/vps-management && LETSENCRYPT_EMAIL=seb.morand@gmail.com ./scripts/letsencrypt.sh obtain slides-content.scm-platform.org && ./scripts/proxy.sh reload"` (the library host certificate is obtained by `vps-deploy.sh` as for every app); (4) data: `ssh vps "mkdir -p /app/data/mcp-htmleditor"`, copy `environments/prod/.env.example` to `/app/data/mcp-htmleditor/.env`, copy the credentials file to `/app/data/mcp-htmleditor/google-oauth.json` with mode 0600 (never in the repository); (5) `make deploy-vps TAG=vX.Y.Z`; (6) verify: `curl -s https://slides.scm-platform.org/health`, `curl -sI http://slides.scm-platform.org/` shows `301` to https, `curl -s -H 'Host: other.example' https://slides.scm-platform.org/` is refused, sign in in a browser; (7) the public static site `lamya-slides.scm-platform.org` is not touched; its availability is checked with `curl -sI https://lamya-slides.scm-platform.org/` before and after.

### Paths

| Path | Action | Note |
|---|---|---|
| `Dockerfile` | modify | copy the seed |
| `docker-compose.prod.yml` | modify | standalone VPS file |
| `environments/prod/.env.example` | create | variables |
| `.dockerignore` | create | build context |
| `Makefile` | modify | `deploy-vps`, `undeploy-vps`, help, `.PHONY` |
| `tests/test_library_deploy.py` | create | static checks of the compose file, Dockerfile, `.dockerignore`, Makefile targets |

### Existing patterns

`notes-mcp/docker-compose.prod.yml` and `notes-mcp/Makefile:422-445` (the owner's convention); `docker-my-services/services/nginx/scripts/vps-deploy.sh` and `proxy.sh`; `Makefile:218-244` (existing docker targets).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

This story maps no test of the spec; its tests are the story tests below.

### Story tests (not spec tests)

`tests/test_library_deploy.py` (story tests, no spec test is mapped here), static checks: (1) `docker-compose.prod.yml` read as text (no YAML dependency exists): holds the service line `  mcp-htmleditor:`, a line `      - "7842"` under `expose:`, no line `ports:`, the lines `proxy-network:` and `external: true`, the `env_file` entry `/app/data/mcp-htmleditor/.env` and the line `command: ["webserve"]`; (2) the `Dockerfile` copies `library-seed/`, keeps `USER appuser:appgroup`, `ENTRYPOINT ["mcp-htmleditor"]` and the `HEALTHCHECK` on `/health`; (3) `.dockerignore` exists and lists `.git`, `.env` and `tests/` and does not list `src/`, `templates/`, `library-seed/`; (4) `make -n deploy-vps TAG=v0.0.0` prints the `vps-deploy.sh`, `proxy.sh add slides-content.scm-platform.org 7842 mcp-htmleditor` and `chown -R 10001:10001` commands and `make -n deploy-vps` without `TAG` exits non zero; (5) `environments/prod/.env.example` holds the seven variables of the contract and no `client_secret`.

## Constraints

- No secret in the repository, the image or a layer; the credentials file is mounted at run time and is never read by anything but `library/signin.py`.
- No `ssh` to the VPS from this story or its tests: the targets are written and statically checked; the first real deployment is the owner's act, after the Google console step.
- Do not edit `docker-compose.yml` or the `run-up` and `run-down` targets.
- Do not touch the public static site.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `README.md` (runbook), `AGENTS.md` (commands), `.agent_docs/docker.md` (the new compose file, the removed overlay), `.agent_docs/makefile.md` (the two targets).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0148: Deployment files and the VPS runbook` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
