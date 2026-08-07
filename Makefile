# Makefile for mcp-htmleditor
# Local, single-user MCP server + WYSIWYG HTML editor.

PYTHON ?= python3
SRC := src
TESTS := tests

.DEFAULT_GOAL := help

.PHONY: sync lint lint-fix format typecheck test test-cov check run clean help

sync: ## Install the package in editable mode with dev dependencies
	$(PYTHON) -m pip install -e .

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
	@echo "  mcp-htmleditor serve <file.html>        Open the WYSIWYG editor in the browser"
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
