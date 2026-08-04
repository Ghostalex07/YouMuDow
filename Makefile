# YouMuDow development tasks
#
# Quick reference:
#   make install     - install package with dev dependencies
#   make run         - launch the desktop app
#   make test        - run the test suite
#   make coverage    - run tests with coverage report
#   make lint        - check lint rules (read-only)
#   make format      - auto-format and auto-fix lint issues
#   make format-check- verify formatting without modifying files
#   make typecheck   - run mypy
#   make check       - run every quality gate

PYTHON := python3
PYTEST := PYTHONPATH=src $(PYTHON) -m pytest
MYPY := PYTHONPATH=src $(PYTHON) -m mypy

.PHONY: install run test coverage lint format format-check typecheck check

install:
	pip install -e ".[dev]"

run:
	$(PYTHON) -m youmudow.main

test:
	$(PYTEST)

coverage:
	$(PYTEST) --cov=src/youmudow --cov-report=term-missing

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

format-check:
	ruff format --check src/ tests/
	ruff check src/ tests/

typecheck:
	$(MYPY)

check: lint format-check typecheck test
