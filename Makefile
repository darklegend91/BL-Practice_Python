.PHONY: install setup crawl cli run test

VENV := .venv/bin

install:
	python3 -m venv .venv
	$(VENV)/pip install -r requirements-dev.txt

# Creates the tables and registers the bundled example sources.
setup:
	$(VENV)/python -m app setup

# Registers the real sources and fetches them. Needs the crawler extra:
#   pip install -r requirements-crawler.txt && python -m playwright install chromium
real:
	LLMFIT_CRAWLER=crawl4ai $(VENV)/python -m app crawl --real

crawl:
	$(VENV)/python -m app crawl

# Ask a question in the terminal.
cli:
	$(VENV)/python -m app ask --interactive

# Start the web API instead.
run:
	$(VENV)/python -m app serve --reload

# No command at all: pick from a menu.
menu:
	$(VENV)/python -m app

test:
	$(VENV)/python -m pytest -q
