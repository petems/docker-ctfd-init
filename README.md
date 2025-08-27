CTFd Initializer

A tiny, CSRF-aware initializer for CTFd that can be run as a one-shot container or script. It detects when CTFd is already configured and, if credentials are provided, performs the initial setup via the web UI.

Features
- Minimal dependencies (`requests` only)
- Idempotent: safe to run multiple times
- Structured JSON logs suitable for containers
- Exponential backoff with jitter and caps
- Small distroless-based Docker image, non-root

Quick Start
- Local: `CTFD_URL=https://ctfd.example.com ADMIN_PASSWORD=secret python ctfd_init.py`
- Docker: `docker run --rm -e CTFD_URL=https://ctfd.example.com -e ADMIN_PASSWORD=secret ghcr.io/<you>/ctfd-init:latest`

Environment Variables
- `CTFD_URL` (required): Base URL, e.g., `https://ctfd.example.com`
- `ADMIN_USERNAME` (optional): Admin display name; default `admin`
- `ADMIN_EMAIL` (optional): Admin email; default `admin@example.com`
- `ADMIN_PASSWORD` (optional): If set, attempt first-time setup; if unset, only detect when already configured
- `PROJECT_NAME` (optional): CTF name; default `CTF`
- `TIMEOUT_SECONDS` (optional): Per-request timeout; default `10`
- `RETRY_ATTEMPTS` (optional): Max polling attempts; default `60`
- `RETRY_BACKOFF_SECONDS` (optional): Initial backoff seconds; default `2`
- `MAX_BACKOFF_SECONDS` (optional): Max backoff cap; default `30`
- `JITTER` (optional): `true`/`false` to randomize backoff; default `true`
- `VERIFY_TLS` (optional): `true`/`false` to verify TLS; default `true`

Exit Codes
- `0`: Already configured or configured successfully
- `10`: Setup not completed after retries (generic)
- `11`: CSRF nonce not found after retries
- `12`: Setup POST failed after retries, or invalid configuration values

Building the Image
- `docker build -t ctfd-initializer .`

Running
- Using an env file: `docker run --rm --env-file .env ctfd-initializer`
- Sidecar/init usage: run alongside CTFd; it exits once setup is complete

Development
- Create venv: `python -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt -r requirements-dev.txt`
- Run tests: `pytest`

Makefile Commands
- `make install`: Create venv and install dependencies
- `make test`: Run tests
- `make lint`: Run Ruff checks
- `make lint-fix`: Auto-fix with Ruff
- `make security`: Run Bandit
- `make build`: Build Docker image
- `make run`: Run Docker image using `.env`
- `make pre-commit`: Install git hooks

Pre-commit Hooks
- Install: `make install && make pre-commit`
- Run on all files once: `. .venv/bin/activate && pre-commit run --all-files`
