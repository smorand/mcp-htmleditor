# =============================================================================
# mcp-htmleditor: multi-stage image (build with `make docker-build`)
# =============================================================================

# =============================================================================
# Stage 1: resolve dependencies and install the package
# =============================================================================
FROM python:3.13-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ARG APP_VERSION=dev

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY templates/ ./templates/
COPY skill/ ./skill/

# Version is injected the same way `make build` does it.
RUN printf '"""Application version.\n\nThe committed value is a placeholder; "make build" and "make docker-build"\noverwrite it from the git tag (git describe --tags --always --dirty).\n"""\n\nfrom __future__ import annotations\n\n__version__: str = "%s"\n' "${APP_VERSION}" > src/mcp_htmleditor/version.py

RUN uv sync --frozen --no-dev --no-editable

# =============================================================================
# Stage 2: runtime
# =============================================================================
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HTMLEDITOR_HOST=0.0.0.0 \
    HTMLEDITOR_PORT=7842 \
    HTMLEDITOR_TEMPLATES_DIR=/app/templates \
    HTMLEDITOR_CACHE_DIR=/var/cache/mcp-htmleditor \
    HTMLEDITOR_LOG_DIR=/var/cache/mcp-htmleditor/logs \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# pandoc is required by the DOCX export.
RUN apt-get update \
    && apt-get install --no-install-recommends -y pandoc \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --shell /bin/false --no-create-home appuser \
    && mkdir -p /data /var/cache/mcp-htmleditor/logs \
    && chown -R appuser:appgroup /data /var/cache/mcp-htmleditor

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/templates /app/templates
COPY --from=builder /app/skill /app/skill

USER appuser:appgroup

EXPOSE 7842

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7842/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["mcp-htmleditor"]
# Documents live in the /data volume; override to serve another file.
CMD ["serve", "--no-browser", "/data/document.html"]
