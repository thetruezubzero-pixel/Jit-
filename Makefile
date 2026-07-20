.PHONY: help install test lint format api frontend-sync frontend-serve

help:
	@echo "Jit — common commands:"
	@echo "  make install         Install the package and dev/test dependencies"
	@echo "  make test            Run the full pytest suite"
	@echo "  make lint            Run flake8 (matches CI)"
	@echo "  make format          Run black over jit/, tests/, examples/, docs/py/bridge.py"
	@echo "  make api             Run the FastAPI backend + frontend at http://localhost:8000"
	@echo "  make frontend-sync   Regenerate docs/py/jit + manifest.json from jit/ (see docs/README)"
	@echo "  make frontend-serve  Serve the static Pyodide phone site at http://localhost:8080"

install:
	python3 -m pip install -r requirements.txt
	python3 -m pip install -e .
	python3 -m pip install pytest pytest-asyncio pytest-cov httpx black flake8

test:
	python3 -m pytest tests/ -v

lint:
	python3 -m flake8 jit/ tests/ docs/py/bridge.py --max-line-length=100 --extend-ignore=E203,W503

format:
	python3 -m black jit/ tests/ examples/ docs/py/bridge.py

api:
	python3 -m jit.api.main

frontend-sync:
	bash scripts/sync_pyodide_source.sh
	@echo "Note: vendoring the Pyodide runtime (docs/vendor/pyodide) is done by"
	@echo ".github/workflows/pages.yml at deploy time, not by this target."

frontend-serve: frontend-sync
	@if [ ! -d docs/vendor/pyodide ]; then \
		echo "docs/vendor/pyodide is missing — run 'npm install --no-save pyodide@0.26.4' in"; \
		echo "docs/ and copy pyodide.mjs/.asm.js/.asm.wasm/-lock.json/python_stdlib.zip there"; \
		echo "first (this is what the pages.yml workflow does automatically)."; \
		exit 1; \
	fi
	cd docs && python3 -m http.server 8080
