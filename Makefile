# Makefile for mcp-htmleditor
# Local, single-user MCP server + WYSIWYG HTML editor.

PYTHON ?= python3
SRC := src
TESTS := tests

# XDG-compliant install targets (all overridable by env)
BIN_DIR       ?= $(HOME)/.local/bin
CONFIG_DIR    ?= $(HOME)/.config/mcp-htmleditor
TEMPLATES_DIR ?= $(CONFIG_DIR)/templates
CACHE_DIR     ?= $(HOME)/.cache/mcp-htmleditor
LOG_DIR       ?= $(CACHE_DIR)/logs
PI_SKILLS_DIR ?= $(HOME)/.pi/agent/dynamic-skills/html-editor

.DEFAULT_GOAL := help

.PHONY: sync install install-skill uninstall lint lint-fix format typecheck test test-cov check run clean help

sync: ## Install the package in editable mode with dev dependencies
	$(PYTHON) -m pip install -e .

install: ## Install CLI (~/.local/bin), templates (~/.config), logs dir (~/.cache), and Pi skill
	@echo "==> Installing mcp-htmleditor package"
	$(PYTHON) -m pip install --user .
	@echo "==> Ensuring bin dir on PATH: $(BIN_DIR)"
	@mkdir -p $(BIN_DIR)
	@# pip --user installs the console script under the user base bin; symlink into BIN_DIR if needed
	@USER_BIN=$$($(PYTHON) -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='posix_user'))"); \
	  if [ -x "$$USER_BIN/mcp-htmleditor" ] && [ "$$USER_BIN" != "$(BIN_DIR)" ]; then \
	    ln -sf "$$USER_BIN/mcp-htmleditor" "$(BIN_DIR)/mcp-htmleditor"; \
	    echo "    linked $$USER_BIN/mcp-htmleditor -> $(BIN_DIR)/mcp-htmleditor"; \
	  fi
	@echo "==> Installing templates into $(TEMPLATES_DIR)"
	@mkdir -p $(TEMPLATES_DIR)
	@cp -R templates/. $(TEMPLATES_DIR)/
	@echo "==> Creating log dir $(LOG_DIR)"
	@mkdir -p $(LOG_DIR)
	@$(MAKE) install-skill
	@echo "==> Done. Ensure $(BIN_DIR) is on your PATH."

install-skill: ## Install the dynamic Pi skill into ~/.pi/agent/dynamic-skills
	@echo "==> Installing dynamic Pi skill into $(PI_SKILLS_DIR)"
	@mkdir -p $(PI_SKILLS_DIR)
	@cp dynamic-skills/html-editor/SKILL.md $(PI_SKILLS_DIR)/SKILL.md
	@echo "    NOTE: add the routing rule to ~/.pi/agent/dynamic_prompt.yaml"
	@echo "          (see dynamic-skills/README.md for the html-editor rule +"
	@echo "           the pptx/docx negative-lookahead variants, zero overlap)."

uninstall: ## Remove installed CLI symlink, templates, logs, and Pi skill
	@rm -f $(BIN_DIR)/mcp-htmleditor
	@rm -rf $(TEMPLATES_DIR) $(LOG_DIR) $(PI_SKILLS_DIR)
	@echo "Removed symlink, templates, logs, and Pi skill. Package: pip uninstall mcp-htmleditor"

lint: ## Run ruff lint checks
	ruff check $(SRC)

lint-fix: ## Run ruff lint with autofix
	ruff check --fix $(SRC)

format: ## Format code with ruff
	ruff format $(SRC)

typecheck: ## Run mypy type checks
	mypy $(SRC)

test: ## Run the test suite
	$(PYTHON) -m pytest $(TESTS)

test-cov: ## Run tests with coverage (gate at 70%)
	$(PYTHON) -m pytest $(TESTS) --cov=mcp_htmleditor --cov-report=term-missing

check: lint typecheck test-cov ## Full quality gate: lint + typecheck + tests with coverage

run: ## Show CLI usage
	@echo "Usage:"
	@echo "  mcp-htmleditor templates                 List available templates"
	@echo "  mcp-htmleditor new <tpl> file.html --serve  Create from template + open editor"
	@echo "  mcp-htmleditor serve <file.html>         Open the WYSIWYG editor in the browser"
	@echo "  mcp-htmleditor skill                     Print the full skill content"
	@echo "  mcp-htmleditor mcp                       Start the MCP server (stdio)"
	@echo "  mcp-htmleditor export pptx in.html out.pptx"
	@echo "  mcp-htmleditor export docx in.html out.docx"

clean: ## Remove build/test/cache artifacts
	rm -rf build dist *.egg-info src/*.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
