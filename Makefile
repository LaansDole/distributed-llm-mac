# ============================================================================
# Code quality targets
# ============================================================================

# Run all linting checks based on .pre-commit-config.yaml
lint:
	@echo "Running linting checks..."
	@echo "✓ Running ruff linter (required)..."
	uv run ruff check src/ tests/ --config pyproject.toml
	@echo ""
	@echo "✓ Running optional linters..."
	@echo "  - yamllint (YAML files)..."
	@uv run yamllint -d "{extends: relaxed, rules: {line-length: disable}}" -s . 2>/dev/null || echo "    ⚠ yamllint not installed (optional)"
	@echo "  - pydocstyle (docstrings)..."
	@uv run pydocstyle src/ 2>/dev/null || echo "    ⚠ pydocstyle not installed (optional)"
	@echo "  - codespell (spelling)..."
	@uv run codespell src/ tests/ 2>/dev/null || echo "    ⚠ codespell not installed (optional)"
	@echo ""
	@echo "✅ All linting checks completed!"

# Format code with ruff
format:
	@echo "Formatting code with ruff..."
	uv run ruff check src/ tests/ --fix --config pyproject.toml
	uv run ruff format src/ tests/ --config pyproject.toml
	@echo "Code formatting completed"
