## Developer Guide: Running with uv + Makefile

This repo uses uv to create and manage the virtual environment and to install dependencies. Day‑to‑day commands are exposed via the Makefile.

### Prerequisites
- Install uv (one‑liner):
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh -s -- -y`
  - After install, the binary is usually at `~/.local/bin/uv`.

### One‑time setup
- Install dependencies into a uv‑managed venv:
  - `make install`
  - If `uv` isn’t on PATH, run: `make UV=$HOME/.local/bin/uv install`

### Common tasks
- Lint: `make lint`
- Lint (auto‑fix + format): `make lint-fix`
- Test: `make test`
- Security scan (Bandit): `make security`
- Build image: `make build`
- Run image: `make run`

Notes
- The Makefile uses uv for environment creation and dependency installation, and invokes tools from the local venv (e.g., `.venv/bin/ruff`).
- If you prefer, you can run tools directly: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, etc.

