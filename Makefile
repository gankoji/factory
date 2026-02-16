PYTHON ?= python3

.PHONY: install test lint typecheck format db-migrate db-downgrade schema-export

install:
	$(PYTHON) -m pip install -e .[dev]

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

typecheck:
	$(PYTHON) -m mypy

format:
	$(PYTHON) -m ruff check --fix src tests

db-migrate:
	$(PYTHON) -m alembic upgrade head

db-downgrade:
	$(PYTHON) -m alembic downgrade -1

schema-export:
	$(PYTHON) scripts/export_schemas.py
