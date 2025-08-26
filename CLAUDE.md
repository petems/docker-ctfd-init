# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

This project uses `uv` for fast dependency management. Set up the development environment:

```bash
# Create virtual environment
uv venv

# Activate environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt -r requirements-dev.txt
```

## Common Commands

### Testing
- **Run unit tests**: `pytest`
- **Run tests with coverage**: `pytest --cov=ctfd_init`
- **Run single test**: `pytest tests/test_init.py::test_function_name`

### Code Quality
- **Run linter**: `ruff check .`
- **Auto-fix linting issues**: `ruff check . --fix`
- **Run security scan**: `bandit -r ctfd_init.py`

### Local Testing
- **Start test CTFd instance**: `docker run -p 8000:8000 -itd --name ctfd-test ctfd/ctfd`
- **Run initializer locally**: `set -a; source .env; set +a && python ctfd_init.py`
- **Clean up test container**: `docker stop ctfd-test && docker rm ctfd-test`

### Docker
- **Build image**: `docker build -t ctfd-initializer .`
- **Run container**: `docker run --rm --env-file .env ctfd-initializer`

## Architecture

This is a single-purpose Python script (`ctfd_init.py`) that initializes CTFd instances through their web interface. The core architecture:

### Main Components
- **Configuration**: Environment variable-based configuration with validation
- **CSRF Handling**: Extracts CSRF nonces from HTML using a tolerant regex
- **Retry Logic**: Exponential backoff with jitter and a max cap
- **Idempotency**: Detects already-configured instances by checking redirect behavior
- **Structured Logging**: JSON-formatted logs for container environments

### Key Functions
- `Config.from_env()`: Loads validated configuration from environment
- `extract_nonce(html)`: Extracts CSRF token from the setup page
- `already_configured(resp)`: Checks if `/setup` redirects
- `post_setup(session, cfg, nonce)`: Submits the setup form
- `configure(cfg)`: Orchestrates polling, setup, and verification
- `main()`: CLI entrypoint returning exit codes

### Environment Configuration
The script is entirely configured through environment variables (see README.md for complete list). Required variable: `CTFD_URL`. If `ADMIN_PASSWORD` is set, the script attempts first-time setup; otherwise it only detects when the instance is already configured.

### Testing Strategy
- Unit tests with `pytest` and `responses` for HTTP mocking
- Acceptance tests run against real CTFd containers
- Security scanning with `bandit`
- CI pipeline with multiple validation stages

## CI/CD Pipeline

The project uses GitHub Actions:
- **Unit Tests**: Full test suite with `pytest`
- **Docker Build**: Builds and optionally pushes to GHCR

All workflows trigger on pushes/PRs to `master` and `main` branches.
