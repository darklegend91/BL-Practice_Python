.PHONY: install db crawl run test

VENV := .venv/bin

install:
	python3 -m venv .venv
	$(VENV)/pip install -r requirements-dev.txt

# Creates the tables, registers the example sources and crawls them.
db:
	$(VENV)/alembic upgrade head
	$(VENV)/python -m app.seed
	$(VENV)/python -m app.crawler

crawl:
	$(VENV)/python -m app.crawler

run:
	$(VENV)/uvicorn app.main:app --reload

test:
	$(VENV)/python -m pytest -q
