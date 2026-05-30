.PHONY: help install test lint format build clean split validate upload upload-wipe upload-wipe-root upload-single

# Default parameters
BACKUP ?= backup.json
CHUNKS ?= ./rtdb-chunks
NODE ?= users
SA ?= ./serviceAccountKey.json
DBPATH ?= /users
UID ?=

help:
	@echo "Available commands:"
	@echo "  make install         - Install package in editable mode with dev dependencies"
	@echo "  make test            - Run Python unit tests"
	@echo "  make lint            - Run linter (Ruff) to check code quality"
	@echo "  make format          - Run formatter (Ruff) to clean up code styling"
	@echo "  make build           - Compile sdist and wheel packages locally"
	@echo "  make clean           - Remove build artifacts, cache files, and temp files"
	@echo ""
	@echo "Restore Workflow:"
	@echo "  make split           - Split backup JSON into chunks (BACKUP=path, CHUNKS=dir, NODE=key)"
	@echo "  make validate        - Losslessly verify chunk integrity (BACKUP=path, CHUNKS=dir, NODE=key)"
	@echo "  make upload          - Batch upload chunks via PATCH (CHUNKS=dir, SA=serviceAccountPath, DBPATH=dbPath)"
	@echo "  make upload-wipe     - Wipe TARGET path first then upload chunks (CHUNKS=dir, SA=serviceAccountPath, DBPATH=dbPath)"
	@echo "  make upload-wipe-root- Wipe ENTIRE database root first then upload chunks"
	@echo "  make upload-single   - Recursively upload single giant user (UID=uid, CHUNKS=chunkFile, SA=serviceAccountPath, DBPATH=dbPath)"

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

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

# Toolkit targets fanned out from python modules
split:
	python3 -m firebase_rtdb_restore.split_backup $(BACKUP) -o $(CHUNKS) -n $(NODE)

validate:
	python3 -m firebase_rtdb_restore.validate_chunks $(BACKUP) $(CHUNKS) -n $(NODE)

upload:
	python3 -m firebase_rtdb_restore.upload_chunks $(CHUNKS) -s $(SA) -p $(DBPATH)

upload-wipe:
	python3 -m firebase_rtdb_restore.upload_chunks $(CHUNKS) -s $(SA) -p $(DBPATH) --wipe

upload-wipe-root:
	python3 -m firebase_rtdb_restore.upload_chunks $(CHUNKS) -s $(SA) -p $(DBPATH) --wipe-root

upload-single:
	python3 -m firebase_rtdb_restore.upload_single_user $(UID) $(CHUNKS) -s $(SA) -p $(DBPATH)
