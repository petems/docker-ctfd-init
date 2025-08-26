.PHONY: help venv install test lint lint-fix security build run clean pre-commit

help:
	@echo "Common targets:"
	@echo "  make install     - create venv and install deps"
	@echo "  make test        - run unit tests"
	@echo "  make lint        - run ruff checks"
	@echo "  make lint-fix    - auto-fix lint issues"
	@echo "  make security    - run bandit scan"
	@echo "  make build       - build Docker image"
	@echo "  make run         - run Docker image with .env"
	@echo "  make pre-commit  - install git hooks"

venv:
	python -m venv .venv

install: venv
	. .venv/bin/activate && \
	pip install -U pip && \
	pip install -r requirements.txt -r requirements-dev.txt

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check .

lint-fix:
	. .venv/bin/activate && ruff check . --fix

security:
	. .venv/bin/activate && bandit -q -r ctfd_init.py

build:
	docker build -t ctfd-initializer .

run:
	docker run --rm --env-file .env ctfd-initializer

pre-commit:
	. .venv/bin/activate && pre-commit install

clean:
	rm -rf .venv .pytest_cache __pycache__

