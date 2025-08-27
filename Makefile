.PHONY: help install test test-unit test-acceptance lint lint-fix security build run clean pre-commit

# Use uv for Python workflows
UV ?= uv
# Default to streaming Docker logs during acceptance tests (can override)
STREAM_DOCKER_LOGS ?= 1

help:
	@echo "Common targets:"
	@echo "  make install        - create uv venv and install deps"
	@echo "  make test           - run unit tests (uv run pytest)"
	@echo "  make test-unit      - run only unit tests"
	@echo "  make test-acceptance- run acceptance tests (requires Docker)"
	@echo "  make lint           - run ruff checks (uv run ruff)"
	@echo "  make lint-fix       - auto-fix + format with ruff"
	@echo "  make security       - run bandit scan"
	@echo "  make build          - build Docker image"
	@echo "  make run            - run Docker image with .env"
	@echo "  make pre-commit     - install git hooks"

install:
	$(UV) sync --dev

test:
	$(UV) run pytest -q -m "not acceptance"

test-unit:
	$(UV) run pytest -q -m "not acceptance"

test-acceptance:
	STREAM_DOCKER_LOGS=$(STREAM_DOCKER_LOGS) $(UV) run pytest -vv -m "acceptance"

lint:
	$(UV) run ruff check .

lint-fix:
	$(UV) run ruff check . --fix
	$(UV) run ruff format

security:
	$(UV) run bandit -q -r ctfd_init.py

build:
	docker build -t ctfd-initializer .

run:
	docker run --rm --env-file .env ctfd-initializer

pre-commit:
	$(UV) run pre-commit install

clean:
	rm -rf .venv .pytest_cache __pycache__
