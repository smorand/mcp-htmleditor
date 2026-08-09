# Makefile for mcp-htmleditor
# Single entry point for every operation: never call uv/ruff/mypy/pytest directly.

.PHONY: sync run run-dev test test-cov lint lint-fix format format-check typecheck \
        security check build install install-skill uninstall docker-build docker-push \
        docker run-up run-down bootstrap-ei clean clean-all info help

PROJECT_NAME=$(shell grep -m1 '^name' pyproject.toml 2>/dev/null | sed 's/.*= *"\([^"]*\)".*/\1/')
PACKAGE := mcp_htmleditor
SRC_DIR := src
TESTS_DIR := tests

# Version injected into the package at build time (git tag driven)
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
VERSION_FILE := $(SRC_DIR)/$(PACKAGE)/version.py

# Writes $(1) as the package version. The generated body is byte identical to the
# committed file when $(1) is "dev", so a build leaves the working tree clean.
define write_version
printf '"""Application version.\n\nThe committed value is a placeholder; "make build" and "make docker-build"\noverwrite it from the git tag (git describe --tags --always --dirty).\n"""\n\nfrom __future__ import annotations\n\n__version__: str = "%s"\n' "$(1)" > $(VERSION_FILE)
endef

PYTHON_VERSION=$(shell python3 --version 2>/dev/null | cut -d' ' -f2)
HAS_UV=$(shell command -v uv >/dev/null 2>&1 && echo "yes" || echo "no")

# Docker configuration
MAKE_DOCKER_PREFIX ?=
DOCKER_TAG ?= latest

# XDG-compliant install targets (all overridable by env)
BIN_DIR       ?= $(HOME)/.local/bin
CONFIG_DIR    ?= $(HOME)/.config/mcp-htmleditor
TEMPLATES_DIR ?= $(CONFIG_DIR)/templates
CACHE_DIR     ?= $(HOME)/.cache/mcp-htmleditor
LOG_DIR       ?= $(CACHE_DIR)/logs
PI_SKILLS_DIR ?= $(HOME)/.pi/agent/dynamic-skills/html-editor

.DEFAULT_GOAL := help

# ============================================================================
# DEPENDENCY MANAGEMENT
# ============================================================================

## sync: Install/update project dependencies using uv (+ Playwright Chromium for E2E tests)
sync:
ifeq ($(HAS_UV),yes)
	@echo "Syncing dependencies with uv..."
	@uv sync
	@echo "Installing Playwright Chromium (fullscreen E2E tests, no-op if already cached)..."
	@uv run playwright install chromium
	@echo "Dependencies synced!"
else
	@echo "Error: uv not found. Install it from https://docs.astral.sh/uv/"
	@exit 1
endif

# ============================================================================
# RUNNING
# ============================================================================

## run: Run the CLI via uv (make run ARGS='export pptx in.html out.pptx')
run: sync
ifdef ARGS
	@uv run $(PROJECT_NAME) $(ARGS)
else
	@uv run $(PROJECT_NAME) --help
endif

## run-dev: Run the CLI module directly from the working tree
run-dev:
ifdef ARGS
	@uv run python -m $(PACKAGE) $(ARGS)
else
	@uv run python -m $(PACKAGE) --help
endif

# ============================================================================
# TESTING
# ============================================================================

## test: Run tests with pytest (make test ARGS='-k test_foo')
test:
	@echo "Running tests..."
ifdef ARGS
	@uv run pytest -v $(ARGS)
else
	@uv run pytest -v
endif
	@echo "Tests complete!"

## test-cov: Run tests with coverage report (gate at 80%)
test-cov:
	@echo "Running tests with coverage..."
	@uv run pytest -v --cov=$(PACKAGE) --cov-report=term-missing
	@echo "Tests complete!"

# ============================================================================
# CODE QUALITY
# ============================================================================

## lint: Check code style with Ruff
lint:
	@echo "Running Ruff linter..."
	@uv run ruff check .
	@echo "Lint check complete!"

## lint-fix: Auto-fix lint issues with Ruff
lint-fix:
	@echo "Running Ruff linter with auto-fix..."
	@uv run ruff check --fix .
	@echo "Lint fix complete!"

## format: Format code with Ruff
format:
	@echo "Formatting code with Ruff..."
	@uv run ruff format .
	@echo "Format complete!"

## format-check: Check code formatting without changes
format-check:
	@echo "Checking code format..."
	@uv run ruff format --check .
	@echo "Format check complete!"

## typecheck: Run type checking with mypy (strict)
typecheck:
	@echo "Running mypy type checker..."
	@uv run mypy $(SRC_DIR)/
	@echo "Type check complete!"

## security: Run bandit security scanner
security:
	@echo "Running bandit security scanner..."
	@uv run bandit -q -r $(SRC_DIR)/ -c pyproject.toml
	@echo "Security scan complete!"

## check: Full quality gate (lint, format, typecheck, security, tests+coverage)
check: lint format-check typecheck security test-cov
	@echo "All checks passed!"

# ============================================================================
# BUILD & INSTALL
# ============================================================================

## build: Build wheel and sdist with the git version injected
build: sync
	@echo "Building $(PROJECT_NAME) $(VERSION)..."
	@$(call write_version,$(VERSION))
	@uv build
	@$(call write_version,dev)
	@echo "Build complete! Artifacts in dist/ (working tree version restored to dev)"

## install: Install the CLI as a uv tool + templates, logs and the Pi skill
install:
ifeq ($(HAS_UV),yes)
	@echo "==> Installing $(PROJECT_NAME) $(VERSION) as a uv tool (bin: $(BIN_DIR))"
	@# A legacy `pip install --user .` copy in the user site-packages shadows
	@# everything else (its console script sits earlier on PATH), so remove it.
	@USER_SITE=$$(python3 -c "import site; print(site.getusersitepackages())"); \
	  if [ -d "$$USER_SITE/$(PACKAGE)" ]; then \
	    echo "    removing legacy pip --user install in $$USER_SITE"; \
	    python3 -m pip uninstall -y -q $(PROJECT_NAME) >/dev/null 2>&1 || true; \
	  fi
	@# A uv tool lives in its own isolated venv: no stale copy in site-packages
	@# can ever shadow the sources, unlike a plain non-editable user install.
	@# The installed snapshot carries the git version, like build and docker-build.
	@$(call write_version,$(VERSION))
	@UV_TOOL_BIN_DIR=$(BIN_DIR) uv tool install . --reinstall --force || ($(call write_version,dev); exit 1)
	@$(call write_version,dev)
	@echo "==> Installing templates into $(TEMPLATES_DIR)"
	@mkdir -p $(TEMPLATES_DIR)
	@cp -R templates/. $(TEMPLATES_DIR)/
	@echo "==> Creating log dir $(LOG_DIR)"
	@mkdir -p $(LOG_DIR)
	@$(MAKE) install-skill
	@echo "==> Done. Ensure $(BIN_DIR) is on your PATH."
else
	@echo "Error: uv not found. Install it from https://docs.astral.sh/uv/"
	@exit 1
endif

## install-skill: Install the dynamic Pi skill into ~/.pi/agent/dynamic-skills
install-skill:
	@echo "==> Installing dynamic Pi skill into $(PI_SKILLS_DIR)"
	@mkdir -p $(PI_SKILLS_DIR)
	@cp dynamic-skills/html-editor/SKILL.md $(PI_SKILLS_DIR)/SKILL.md
	@echo "    NOTE: add the routing rule to ~/.pi/agent/dynamic_prompt.yaml"
	@echo "          (see dynamic-skills/README.md for the html-editor rule +"
	@echo "           the pptx/docx negative-lookahead variants, zero overlap)."

## uninstall: Remove the uv tool, templates, logs and the Pi skill
uninstall:
	@echo "Uninstalling $(PROJECT_NAME)..."
	@UV_TOOL_BIN_DIR=$(BIN_DIR) uv tool uninstall $(PROJECT_NAME) 2>/dev/null || echo "    tool not installed"
	@rm -f $(BIN_DIR)/mcp-htmleditor
	@rm -rf $(TEMPLATES_DIR) $(LOG_DIR) $(PI_SKILLS_DIR)
	@echo "Uninstall complete!"

# ============================================================================
# DOCKER
# ============================================================================

## docker-build: Build the Docker image with the git version injected
docker-build:
	@echo "Building Docker image: $(MAKE_DOCKER_PREFIX)$(PROJECT_NAME):$(DOCKER_TAG) (version $(VERSION))..."
	@docker build --build-arg APP_VERSION=$(VERSION) -t $(MAKE_DOCKER_PREFIX)$(PROJECT_NAME):$(DOCKER_TAG) .
	@echo "Docker image built!"

## docker-push: Push the Docker image to the registry
docker-push:
	@echo "Pushing Docker image: $(MAKE_DOCKER_PREFIX)$(PROJECT_NAME):$(DOCKER_TAG)..."
	@docker push $(MAKE_DOCKER_PREFIX)$(PROJECT_NAME):$(DOCKER_TAG)
	@echo "Docker image pushed!"

## docker: Build and push the Docker image
docker: docker-build docker-push

## run-up: Build the image and start docker compose
run-up: docker-build
	@echo "Starting services..."
	@PROJECT_NAME=$(PROJECT_NAME) DOCKER_PREFIX=$(MAKE_DOCKER_PREFIX) DOCKER_TAG=$(DOCKER_TAG) \
	  APP_VERSION=$(VERSION) docker compose up -d
	@echo "Services started on http://localhost:7842/"

## run-down: Stop docker compose services
run-down:
	@echo "Stopping services..."
	@PROJECT_NAME=$(PROJECT_NAME) DOCKER_PREFIX=$(MAKE_DOCKER_PREFIX) DOCKER_TAG=$(DOCKER_TAG) \
	  docker compose down
	@echo "Services stopped!"

# ============================================================================
# PROJECT SPECIFIC
# ============================================================================

## bootstrap-ei: Regenerate the EI slides bootstrap from the EI reference
bootstrap-ei:
	@uv run python tools/gen_ei_bootstrap.py

# ============================================================================
# CLEANUP
# ============================================================================

## clean: Remove caches and build artifacts
clean:
	@echo "Cleaning up..."
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -rf dist build *.egg-info $(SRC_DIR)/*.egg-info
	@rm -rf .coverage htmlcov
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Clean complete!"

## clean-all: Remove everything including the venv and the lock file
clean-all: clean
	@echo "Removing virtual environment and lock file..."
	@rm -rf .venv
	@rm -f uv.lock
	@echo "Full clean complete!"

# ============================================================================
# INFORMATION
# ============================================================================

## info: Show project information
info:
	@echo "Project Information"
	@echo "==================="
	@echo "Project name:    $(PROJECT_NAME)"
	@echo "Package:         $(PACKAGE)"
	@echo "Version:         $(VERSION)"
	@echo "Source dir:      $(SRC_DIR)/"
	@echo "Python version:  $(PYTHON_VERSION)"
	@echo "uv available:    $(HAS_UV)"
	@echo "Install targets:"
	@echo "  bin            $(BIN_DIR)"
	@echo "  templates      $(TEMPLATES_DIR)"
	@echo "  logs           $(LOG_DIR)"
	@echo "  pi skill       $(PI_SKILLS_DIR)"

## help: Show this help message
help:
	@echo "mcp-htmleditor Makefile"
	@echo "======================="
	@echo ""
	@echo "Dependency Management:"
	@echo "  sync             - Install/update dependencies with uv"
	@echo ""
	@echo "Running:"
	@echo "  run              - Run the CLI via uv (ARGS='...')"
	@echo "  run-dev          - Run the CLI module from the working tree (ARGS='...')"
	@echo ""
	@echo "Testing:"
	@echo "  test             - Run tests with pytest (ARGS='-k test_foo')"
	@echo "  test-cov         - Run tests with coverage (gate 80%)"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             - Check code style with Ruff"
	@echo "  lint-fix         - Auto-fix lint issues"
	@echo "  format           - Format code with Ruff"
	@echo "  format-check     - Check formatting without changes"
	@echo "  typecheck        - Run mypy (strict)"
	@echo "  security         - Run bandit security scanner"
	@echo "  check            - Full gate: lint, format-check, typecheck, security, test-cov"
	@echo ""
	@echo "Build & Install:"
	@echo "  build            - Build wheel and sdist (version from git tag)"
	@echo "  install          - Install CLI as uv tool + templates, logs, Pi skill"
	@echo "  install-skill    - Install the dynamic Pi skill only"
	@echo "  uninstall        - Remove tool, templates, logs, Pi skill"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build     - Build the image (APP_VERSION from git)"
	@echo "  docker-push      - Push the image"
	@echo "  docker           - Build and push"
	@echo "  run-up           - Build and start docker compose"
	@echo "  run-down         - Stop docker compose"
	@echo ""
	@echo "Project specific:"
	@echo "  bootstrap-ei     - Regenerate the EI bootstrap from the EI reference"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            - Remove caches and build artifacts"
	@echo "  clean-all        - Remove everything including .venv and uv.lock"
	@echo ""
	@echo "Information:"
	@echo "  info             - Show project information"
	@echo "  help             - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make check"
	@echo "  make run ARGS='export pptx in.html out.pptx'"
	@echo "  make test ARGS='-k pptx'"
	@echo "  MAKE_DOCKER_PREFIX=ghcr.io/smorand/ DOCKER_TAG=v1.0.0 make docker"
