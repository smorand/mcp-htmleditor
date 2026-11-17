"""US-0148: the deployment files of the web library mode (SPEC-0025, DEC-046, DEC-047).

Static checks only: nothing here starts a container or reaches a server. The compose file is read as text (the project
has no YAML dependency); ``make -n`` prints what a deployment would run without running it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MAKE = shutil.which("make") or "make"
GIT = shutil.which("git") or "git"
COMPOSE = (REPO / "docker-compose.prod.yml").read_text(encoding="utf-8")
DOCKERFILE = (REPO / "Dockerfile").read_text(encoding="utf-8")
ENVIRONMENT = REPO / "environments" / "prod" / ".env.example"
SEVEN_VARIABLES = (
    "HTMLEDITOR_HOST",
    "HTMLEDITOR_PORT",
    "HTMLEDITOR_LIBRARY_ORIGIN",
    "HTMLEDITOR_LIBRARY_CONTENT_ORIGIN",
    "HTMLEDITOR_LIBRARY_DIR",
    "HTMLEDITOR_STATE_DIR",
    "HTMLEDITOR_GOOGLE_CREDENTIALS_FILE",
)


def make(*arguments: str) -> subprocess.CompletedProcess[str]:
    """``make -n`` of a target: the recipe is printed, never run."""
    return subprocess.run(  # noqa: S603 - the make binary with fixed target names
        [MAKE, "-n", *arguments], cwd=REPO, capture_output=True, text=True, timeout=60, check=False
    )


def lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if not line.lstrip().startswith("#")]


def test_the_compose_file_is_the_standalone_vps_file() -> None:
    body = lines(COMPOSE)

    assert "  mcp-htmleditor:" in body
    assert "    container_name: mcp-htmleditor" in body
    assert '    command: ["webserve"]' in body
    assert "    expose:" in body
    assert '      - "7842"' in body
    assert not [line for line in body if re.match(r"\s*ports:", line)]
    assert "  proxy-network:" in body
    assert "    external: true" in body
    assert "      - /app/data/mcp-htmleditor/.env" in body
    assert "      - /app/data/mcp-htmleditor:/data" in body
    assert "        APP_VERSION: ${APP_VERSION:-dev}" in body
    assert "      driver: json-file" in body
    assert "    restart: unless-stopped" in body


def test_the_compose_file_holds_no_secret_and_does_not_extend_the_local_stack() -> None:
    assert not re.search(r"(?i)client_secret|password|api_key\s*:\s*\S", COMPOSE)
    assert "docker-compose.yml" not in "\n".join(lines(COMPOSE))
    assert (REPO / "docker-compose.yml").read_text(encoding="utf-8").count("ports:") == 1  # the local file is untouched


def test_the_dockerfile_copies_the_seed_and_keeps_its_guarantees() -> None:
    body = lines(DOCKERFILE)

    assert "COPY library-seed/ ./library-seed/" in body
    assert body.index("COPY skill/ ./skill/") < body.index("COPY library-seed/ ./library-seed/")
    assert "USER appuser:appgroup" in body
    assert 'ENTRYPOINT ["mcp-htmleditor"]' in body
    assert any(line.startswith("HEALTHCHECK") for line in body)
    assert any("/health" in line for line in body)
    assert "chromium" not in DOCKERFILE.lower()


def test_dockerignore_keeps_the_build_inputs_and_drops_the_rest() -> None:
    ignored = {
        line.strip() for line in (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines() if line.strip()
    }

    assert {".git", ".env", "tests/", "sdlc/", ".venv"} <= ignored
    assert ignored.isdisjoint(
        {"src/", "src", "templates/", "templates", "library-seed/", "library-seed", "skill/", "skill"}
    )
    assert ignored.isdisjoint({"pyproject.toml", "uv.lock", "README.md"})


def test_deploy_vps_prints_the_deployment_steps_and_needs_a_tag() -> None:
    printed = make("deploy-vps", "TAG=v0.0.0")

    assert printed.returncode == 0, printed.stderr
    assert (
        "vps-deploy.sh smorand/mcp-htmleditor@v0.0.0 prod slides.scm-platform.org:7842 ./environments" in printed.stdout
    )
    assert "proxy.sh add slides-content.scm-platform.org 7842 mcp-htmleditor" in printed.stdout
    assert "chown -R 10001:10001 /app/data/mcp-htmleditor" in printed.stdout
    assert "docker compose -f docker-compose.prod.yml" in printed.stdout
    assert "git tag -f v0.0.0" in printed.stdout
    assert "ssh vps" in printed.stdout
    assert make("deploy-vps").returncode != 0


def test_undeploy_vps_keeps_the_data() -> None:
    printed = make("undeploy-vps")

    assert printed.returncode == 0, printed.stderr
    assert "vps-undeploy.sh" in printed.stdout
    assert "rm -rf /app/data" not in printed.stdout
    assert "chown" not in printed.stdout


def test_the_deploy_targets_are_phony_and_listed_by_make_help() -> None:
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    phony = makefile.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    assert "deploy-vps" in phony
    assert "undeploy-vps" in phony
    helped = subprocess.run([MAKE, "help"], cwd=REPO, capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
    assert "deploy-vps" in helped.stdout
    assert "undeploy-vps" in helped.stdout


def test_the_environment_example_holds_the_seven_variables_and_no_secret() -> None:
    text = ENVIRONMENT.read_text(encoding="utf-8")
    active = dict(
        line.split("=", 1) for line in text.splitlines() if line.strip() and not line.startswith("#") and "=" in line
    )

    assert set(SEVEN_VARIABLES) <= set(active)
    assert active["HTMLEDITOR_HOST"] == "0.0.0.0"
    assert active["HTMLEDITOR_LIBRARY_ORIGIN"] == "https://slides.scm-platform.org"
    assert active["HTMLEDITOR_LIBRARY_CONTENT_ORIGIN"] == "https://slides-content.scm-platform.org"
    assert active["HTMLEDITOR_LIBRARY_DIR"] == "/data/library"
    assert active["HTMLEDITOR_STATE_DIR"] == "/data/state"
    assert active["HTMLEDITOR_GOOGLE_CREDENTIALS_FILE"] == "/data/google-oauth.json"
    assert "client_secret" not in text.lower()
    assert "# HTMLEDITOR_OTEL_DESTINATION" in text
    assert "# HTMLEDITOR_OTEL_API_KEY" in text


@pytest.mark.parametrize("path", ["environments/prod/.env.example"])
def test_the_environment_example_is_not_ignored_by_git(path: str) -> None:
    ignored = subprocess.run([GIT, "check-ignore", "-q", path], cwd=REPO, check=False)  # noqa: S603
    assert ignored.returncode == 1
