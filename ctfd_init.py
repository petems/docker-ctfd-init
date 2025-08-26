#!/usr/bin/env python3
"""CTFd initializer script.

This script performs the first-boot setup for CTFd in a CSRF-aware manner.
It is intentionally minimal and relies only on the Python standard library
plus the `requests` package for HTTP interactions.

The behaviour is driven by environment variables as documented in
`DOCKER_SPEC.md`.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass

import requests

LOG = logging.getLogger("ctfd_init")


class SetupError(RuntimeError):
    """Raised when the setup process ultimately fails."""

    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class Config:
    ctfd_url: str
    admin_username: str | None
    admin_email: str | None
    admin_password: str | None
    project_name: str = "CTF"
    timeout: int = 10
    attempts: int = 60
    backoff: int = 2
    max_backoff: int = 30
    jitter: bool = True
    verify_tls: bool = True

    @classmethod
    def from_env(cls) -> Config:
        ctfd_url = os.environ.get("CTFD_URL")
        if not ctfd_url:
            raise SetupError("CTFD_URL is required", exit_code=12)

        try:
            timeout = int(os.environ.get("TIMEOUT_SECONDS", "10"))
            attempts = int(os.environ.get("RETRY_ATTEMPTS", "60"))
            backoff = int(os.environ.get("RETRY_BACKOFF_SECONDS", "2"))
        except ValueError as e:
            raise SetupError(
                f"Invalid integer value in environment variable: {e}", exit_code=12
            ) from e

        return cls(
            ctfd_url=ctfd_url.rstrip("/"),
            admin_username=os.environ.get("ADMIN_USERNAME"),
            admin_email=os.environ.get("ADMIN_EMAIL"),
            admin_password=os.environ.get("ADMIN_PASSWORD"),
            project_name=os.environ.get("PROJECT_NAME", "CTF"),
            timeout=timeout,
            attempts=attempts,
            backoff=backoff,
            max_backoff=int(os.environ.get("MAX_BACKOFF_SECONDS", "30")),
            jitter=os.environ.get("JITTER", "true").lower() == "true",
            verify_tls=os.environ.get("VERIFY_TLS", "true").lower() == "true",
        )


def extract_nonce(html: str) -> str | None:
    """Extract CSRF nonce from setup HTML."""
    match = re.search(r"name=['\"]nonce['\"]\s+value=['\"]([^'\"]+)['\"]", html)
    if match:
        return match.group(1)
    return None


def already_configured(response: requests.Response) -> bool:
    """Return True if the /setup endpoint redirects away, meaning configured."""
    return 300 <= response.status_code < 400


def post_setup(session: requests.Session, cfg: Config, nonce: str) -> requests.Response:
    data = {
        "nonce": nonce,
        "ctf_name": cfg.project_name,
        "name": cfg.admin_username or "admin",
        "email": cfg.admin_email or "admin@example.com",
        "password": cfg.admin_password or "",
        "ctf_description": "",
        "theme": "core",
        "ctf_timezone": "UTC",
        "lang": "en",
    }
    return session.post(
        f"{cfg.ctfd_url}/setup",
        data=data,
        allow_redirects=False,
        timeout=cfg.timeout,
        verify=cfg.verify_tls,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _sleep_with_backoff(cfg: Config, attempt: int) -> None:
    base = min(cfg.max_backoff, cfg.backoff * (2 ** (attempt - 1)))
    if cfg.jitter:
        # Use cryptographically strong randomness to avoid Bandit B311
        # (not security-critical here, but keeps scanners happy):
        jitter_unit = secrets.randbelow(10_000) / 10_000.0  # [0.0, 1.0)
        delay = base * (0.5 + jitter_unit * 0.5)
    else:
        delay = base
    time.sleep(delay)


def configure(cfg: Config) -> None:
    session = requests.Session()
    last_error: str | None = None
    for attempt in range(1, cfg.attempts + 1):
        start = time.time()
        try:
            resp = session.get(
                f"{cfg.ctfd_url}/setup",
                allow_redirects=False,
                timeout=cfg.timeout,
                verify=cfg.verify_tls,
            )
        except requests.RequestException as e:
            last_error = f"request error: {e}"
            LOG.warning(
                json.dumps(
                    {
                        "level": "warning",
                        "ts": datetime.datetime.now(datetime.UTC).isoformat(),
                        "msg": "GET /setup failed",
                        "error": str(e),
                        "attempt": attempt,
                    }
                )
            )
            _sleep_with_backoff(cfg, attempt)
            continue
        elapsed = int((time.time() - start) * 1000)
        LOG.info(
            json.dumps(
                {
                    "level": "info",
                    "ts": datetime.datetime.now(datetime.UTC).isoformat(),
                    "attempt": attempt,
                    "status": resp.status_code,
                    "url": f"{cfg.ctfd_url}/setup",
                    "elapsed_ms": elapsed,
                    "msg": "GET /setup",
                }
            )
        )
        if already_configured(resp):
            LOG.info(
                json.dumps(
                    {
                        "level": "info",
                        "ts": datetime.datetime.now(datetime.UTC).isoformat(),
                        "msg": "Already configured",
                    }
                )
            )
            return
        nonce = extract_nonce(resp.text)
        if cfg.admin_password:
            if nonce:
                post_resp = post_setup(session, cfg, nonce)
                if not 300 <= post_resp.status_code < 400:
                    LOG.warning(
                        json.dumps(
                            {
                                "level": "warning",
                                "ts": datetime.datetime.now(datetime.UTC).isoformat(),
                                "msg": "POST to /setup did not result in a redirect",
                                "status": post_resp.status_code,
                            }
                        )
                    )
                # verify
                try:
                    verify_resp = session.get(
                        f"{cfg.ctfd_url}/setup",
                        allow_redirects=False,
                        timeout=cfg.timeout,
                        verify=cfg.verify_tls,
                    )
                except requests.RequestException as e:
                    last_error = f"verify error: {e}"
                    _sleep_with_backoff(cfg, attempt)
                    continue
                if already_configured(verify_resp):
                    LOG.info(
                        json.dumps(
                            {
                                "level": "info",
                                "ts": datetime.datetime.now(datetime.UTC).isoformat(),
                                "msg": "Configured successfully",
                            }
                        )
                    )
                    return
                last_error = "setup POST did not complete configuration"
            else:
                last_error = "nonce not found in setup page"
        _sleep_with_backoff(cfg, attempt)
    if last_error == "nonce not found in setup page":
        raise SetupError("nonce not found after retries", exit_code=11)
    if last_error == "setup POST did not complete configuration":
        raise SetupError("setup POST failed after retries", exit_code=12)
    raise SetupError("setup not completed after retries", exit_code=10)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        cfg = Config.from_env()
        configure(cfg)
    except SetupError as exc:
        LOG.error(
            json.dumps(
                {
                    "level": "error",
                    "ts": datetime.datetime.now(datetime.UTC).isoformat(),
                    "msg": str(exc),
                }
            )
        )
        return exc.exit_code
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
