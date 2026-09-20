.PHONY: install db seed api crawler scheduler test test-unit test-integration test-contracts migrate

VENV := .venv/bin

install:
	python3 -m venv .venv
	$(VENV)/pip install -r requirements-dev.txt

db:
	PATH="$(PWD)/$(VENV):$$PATH" ./scripts/setup-local-database.sh

migrate:
	$(VENV)/alembic upgrade head

seed:
	$(VENV)/python -m app.seed.load

api:
	$(VENV)/uvicorn app.main:app --reload --port 8000

crawler:
	$(VENV)/python -m app.workers.crawler

scheduler:
	$(VENV)/python -m app.workers.scheduler

test:
	$(VENV)/python -m pytest -q

test-unit:
	$(VENV)/python -m pytest tests/unit -q

test-integration:
	$(VENV)/python -m pytest tests/integration -q

test-contracts:
	$(VENV)/python -m pytest tests/contracts -q
