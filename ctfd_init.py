#!/usr/bin/env python3
"""CTFd initializer script.

This script performs the first-boot setup for CTFd in a CSRF-aware manner.
It is intentionally minimal and relies only on the Python standard library
plus the `requests` package for HTTP interactions.

The behaviour is driven by environment variables as documented in
`DOCKER_SPEC.md`.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

import requests

LOG = logging.getLogger("ctfd_init")


class SetupError(RuntimeError):
    """Raised when the setup process ultimately fails."""


@dataclass
class Config:
    ctfd_url: str
    admin_username: Optional[str]
    admin_email: Optional[str]
    admin_password: Optional[str]
    project_name: str = "CTF"
    timeout: int = 10
    attempts: int = 60
    backoff: int = 2
    verify_tls: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
            value = os.environ.get(name, default)
            return value

        ctfd_url = os.environ.get("CTFD_URL")
        if not ctfd_url:
            raise SetupError("CTFD_URL is required")
        return cls(
            ctfd_url=ctfd_url.rstrip("/"),
            admin_username=getenv("ADMIN_USERNAME"),
            admin_email=getenv("ADMIN_EMAIL"),
            admin_password=getenv("ADMIN_PASSWORD"),
            project_name=getenv("PROJECT_NAME", "CTF"),
            timeout=int(getenv("TIMEOUT_SECONDS", "10")),
            attempts=int(getenv("RETRY_ATTEMPTS", "60")),
            backoff=int(getenv("RETRY_BACKOFF_SECONDS", "2")),
            verify_tls=getenv("VERIFY_TLS", "true").lower() == "true",
        )


def extract_nonce(html: str) -> Optional[str]:
    """Extract CSRF nonce from setup HTML."""
    match = re.search(r'name=[\"\']nonce[\"\']\s+value=[\"\']([^\"\']+)[\"\']', html)
    if match:
        return match.group(1)
    return None


def already_configured(response: requests.Response) -> bool:
    """Return True if the /setup endpoint redirects away, meaning configured."""
    return 300 <= response.status_code < 400


def post_setup(session: requests.Session, cfg: Config, nonce: str) -> None:
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
    session.post(
        f"{cfg.ctfd_url}/setup",
        data=data,
        allow_redirects=False,
        timeout=cfg.timeout,
        verify=cfg.verify_tls,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def configure(cfg: Config) -> None:
    session = requests.Session()
    for attempt in range(1, cfg.attempts + 1):
        start = time.time()
        resp = session.get(
            f"{cfg.ctfd_url}/setup",
            allow_redirects=False,
            timeout=cfg.timeout,
            verify=cfg.verify_tls,
        )
        elapsed = int((time.time() - start) * 1000)
        LOG.info(json.dumps({
            "level": "info",
            "attempt": attempt,
            "status": resp.status_code,
            "url": f"{cfg.ctfd_url}/setup",
            "elapsed_ms": elapsed,
            "msg": "GET /setup"
        }))
        if already_configured(resp):
            LOG.info(json.dumps({"level": "info", "msg": "Already configured"}))
            return
        nonce = extract_nonce(resp.text)
        if nonce and cfg.admin_password:
            post_setup(session, cfg, nonce)
            # verify
            verify_resp = session.get(
                f"{cfg.ctfd_url}/setup",
                allow_redirects=False,
                timeout=cfg.timeout,
                verify=cfg.verify_tls,
            )
            if already_configured(verify_resp):
                LOG.info(json.dumps({"level": "info", "msg": "Configured successfully"}))
                return
        time.sleep(cfg.backoff)
    raise SetupError("setup not completed after retries")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        cfg = Config.from_env()
        configure(cfg)
    except SetupError as exc:
        LOG.error(json.dumps({"level": "error", "msg": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())

