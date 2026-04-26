.PHONY: setup clean test sync install

# Create Hermes plugin entry point (root __init__.py for plugin.yaml compatibility)
setup:
	@echo "Creating Hermes plugin entry point..."
	@printf '"""Hermes Portfolio Manager plugin entry point."""\nfrom portfolio_manager import register\n__all__ = ["register"]\n' > __init__.py
	@echo "Done."

install:
	uv venv --python 3.11
	uv pip install -e ".[dev]"

sync:
	uv pip install -e ".[dev]"

test:
	uv run pytest --tb=short -q

clean:
	rm -f __init__.py
