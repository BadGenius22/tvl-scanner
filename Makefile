.PHONY: help install lint fix typecheck test check

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package with dev extras (editable)
	pip install -e ".[dev]"

lint:  ## Lint src/ and tests/ (no changes)
	ruff check src/ tests/

fix:  ## Auto-fix lint issues where safe
	ruff check --fix src/ tests/

typecheck:  ## Strict type check of src/
	mypy src/

test:  ## Run the test suite (HTTP is mocked; no secrets needed)
	pytest -q

check: lint typecheck test  ## Run the full gate: lint + typecheck + test
	@echo "✓ all checks passed"
