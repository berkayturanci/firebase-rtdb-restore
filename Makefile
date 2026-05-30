.PHONY: help install test lint format build clean

help:
	@echo "Available commands:"
	@echo "  make install  - Install package in editable mode with development dependencies"
	@echo "  make test     - Run Python unit tests"
	@echo "  make lint     - Run linter (Ruff) to check code quality"
	@echo "  make format   - Run formatter (Ruff) to clean up code styling"
	@echo "  make build    - Compile sdist and wheel packages locally"
	@echo "  make clean    - Remove build artifacts, cache files, and temp files"

install:
	pip install --upgrade pip
	pip install -e .[dev]
	pip install ruff build pre-commit

test:
	python3 -m unittest discover tests/ -p "test_*.py"

lint:
	ruff check .

format:
	ruff format .

build:
	python3 -m build --sdist --wheel --outdir dist/

clean:
	rm -rf build/ dist/ *.egg-info/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
