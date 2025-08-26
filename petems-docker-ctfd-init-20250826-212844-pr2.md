# petems/docker-ctfd-init - PR #2 Review Comments
**Repository:** petems/docker-ctfd-init
**Pull Request:** https://github.com/petems/docker-ctfd-init/pull/2
**Total Comments:** 7

---

## Comment #1
**Author:** @gemini-code-assist
**File:** `ctfd_init.py`
**Line:** 62
**Created:** 2025-08-26 20:15:04 UTC
**Updated:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,152 @@
+#!/usr/bin/env python3
+"""CTFd initializer script.
+
+This script performs the first-boot setup for CTFd in a CSRF-aware manner.
+It is intentionally minimal and relies only on the Python standard library
+plus the `requests` package for HTTP interactions.
+
+The behaviour is driven by environment variables as documented in
+`DOCKER_SPEC.md`.
+"""
+from __future__ import annotations
+
+import json
+import logging
+import os
+import re
+import sys
+import time
+from dataclasses import dataclass
+from typing import Optional
+
+import requests
+
+LOG = logging.getLogger("ctfd_init")
+
+
+class SetupError(RuntimeError):
+    """Raised when the setup process ultimately fails."""
+
+
+@dataclass
+class Config:
+    ctfd_url: str
+    admin_username: Optional[str]
+    admin_email: Optional[str]
+    admin_password: Optional[str]
+    project_name: str = "CTF"
+    timeout: int = 10
+    attempts: int = 60
+    backoff: int = 2
+    verify_tls: bool = True
+
+    @classmethod
+    def from_env(cls) -> "Config":
+        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
+            value = os.environ.get(name, default)
+            return value
+
+        ctfd_url = os.environ.get("CTFD_URL")
+        if not ctfd_url:
+            raise SetupError("CTFD_URL is required")
+        return cls(
+            ctfd_url=ctfd_url.rstrip("/"),
+            admin_username=getenv("ADMIN_USERNAME"),
+            admin_email=getenv("ADMIN_EMAIL"),
+            admin_password=getenv("ADMIN_PASSWORD"),
+            project_name=getenv("PROJECT_NAME", "CTF"),
+            timeout=int(getenv("TIMEOUT_SECONDS", "10")),
+            attempts=int(getenv("RETRY_ATTEMPTS", "60")),
+            backoff=int(getenv("RETRY_BACKOFF_SECONDS", "2")),
+            verify_tls=getenv("VERIFY_TLS", "true").lower() == "true",
+        )
```

### Comment
![high](https://www.gstatic.com/codereviewagent/high-priority.svg)

The `from_env` method can be improved in two ways. First, the nested `getenv` function is redundant as it just wraps `os.environ.get`. It can be removed for simplicity. Second, and more importantly, the calls to `int()` are not wrapped in a try-except block, which will cause the script to crash with a `ValueError` if non-integer values are provided for timeout, attempts, or backoff. This should be handled gracefully to prevent the container from crashing on invalid configuration.

```python
    def from_env(cls) -> "Config":
        ctfd_url = os.environ.get("CTFD_URL")
        if not ctfd_url:
            raise SetupError("CTFD_URL is required")

        try:
            timeout = int(os.environ.get("TIMEOUT_SECONDS", "10"))
            attempts = int(os.environ.get("RETRY_ATTEMPTS", "60"))
            backoff = int(os.environ.get("RETRY_BACKOFF_SECONDS", "2"))
        except ValueError as e:
            raise SetupError(f"Invalid integer value in environment variable: {e}") from e

        return cls(
            ctfd_url=ctfd_url.rstrip("/"),
            admin_username=os.environ.get("ADMIN_USERNAME"),
            admin_email=os.environ.get("ADMIN_EMAIL"),
            admin_password=os.environ.get("ADMIN_PASSWORD"),
            project_name=os.environ.get("PROJECT_NAME", "CTF"),
            timeout=timeout,
            attempts=attempts,
            backoff=backoff,
            verify_tls=os.environ.get("VERIFY_TLS", "true").lower() == "true",
        )
```

---

## Comment #2
**Author:** @gemini-code-assist
**File:** `Dockerfile`
**Line:** 10
**Created:** 2025-08-26 20:15:04 UTC
**Updated:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,10 @@
+# syntax=docker/dockerfile:1.4
+
+FROM python:3.12-alpine AS base
+WORKDIR /app
+COPY requirements.txt .
+RUN pip install --no-cache-dir -r requirements.txt
+COPY ctfd_init.py ./ctfd_init.py
+RUN adduser -D -H -u 65532 appuser
+USER 65532
+ENTRYPOINT ["python", "/app/ctfd_init.py"]
```

### Comment
![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

This Dockerfile is a good start, but it can be improved by using a multi-stage build to create a smaller and more secure final image. This aligns with the "Minimal image and security posture" section of your DOCKER_SPEC.md, which recommends using a distroless image for the final stage. A multi-stage build separates the build environment from the runtime environment, reducing the attack surface of the final image.

```
FROM python:3.12-alpine AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/usr/local -r requirements.txt
COPY ctfd_init.py .

FROM gcr.io/distroless/python3-debian12
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app/ctfd_init.py .
RUN adduser -D -H -u 65532 appuser
USER 65532
ENTRYPOINT ["python", "/app/ctfd_init.py"]
```

---

## Comment #3
**Author:** @gemini-code-assist
**File:** `ctfd_init.py`
**Line:** 97
**Created:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,152 @@
+#!/usr/bin/env python3
+"""CTFd initializer script.
+
+This script performs the first-boot setup for CTFd in a CSRF-aware manner.
+It is intentionally minimal and relies only on the Python standard library
+plus the `requests` package for HTTP interactions.
+
+The behaviour is driven by environment variables as documented in
+`DOCKER_SPEC.md`.
+"""
+from __future__ import annotations
+
+import json
+import logging
+import os
+import re
+import sys
+import time
+from dataclasses import dataclass
+from typing import Optional
+
+import requests
+
+LOG = logging.getLogger("ctfd_init")
+
+
+class SetupError(RuntimeError):
+    """Raised when the setup process ultimately fails."""
+
+
+@dataclass
+class Config:
+    ctfd_url: str
+    admin_username: Optional[str]
+    admin_email: Optional[str]
+    admin_password: Optional[str]
+    project_name: str = "CTF"
+    timeout: int = 10
+    attempts: int = 60
+    backoff: int = 2
+    verify_tls: bool = True
+
+    @classmethod
+    def from_env(cls) -> "Config":
+        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
+            value = os.environ.get(name, default)
+            return value
+
+        ctfd_url = os.environ.get("CTFD_URL")
+        if not ctfd_url:
+            raise SetupError("CTFD_URL is required")
+        return cls(
+            ctfd_url=ctfd_url.rstrip("/"),
+            admin_username=getenv("ADMIN_USERNAME"),
+            admin_email=getenv("ADMIN_EMAIL"),
+            admin_password=getenv("ADMIN_PASSWORD"),
+            project_name=getenv("PROJECT_NAME", "CTF"),
+            timeout=int(getenv("TIMEOUT_SECONDS", "10")),
+            attempts=int(getenv("RETRY_ATTEMPTS", "60")),
+            backoff=int(getenv("RETRY_BACKOFF_SECONDS", "2")),
+            verify_tls=getenv("VERIFY_TLS", "true").lower() == "true",
+        )
+
+
+def extract_nonce(html: str) -> Optional[str]:
+    """Extract CSRF nonce from setup HTML."""
+    match = re.search(r'name=[\"\']nonce[\"\']\s+value=[\"\']([^\"\']+)[\"\']', html)
+    if match:
+        return match.group(1)
+    return None
+
+
+def already_configured(response: requests.Response) -> bool:
+    """Return True if the /setup endpoint redirects away, meaning configured."""
+    return 300 <= response.status_code < 400
+
+
+def post_setup(session: requests.Session, cfg: Config, nonce: str) -> None:
+    data = {
+        "nonce": nonce,
+        "ctf_name": cfg.project_name,
+        "name": cfg.admin_username or "admin",
+        "email": cfg.admin_email or "admin@example.com",
+        "password": cfg.admin_password or "",
+        "ctf_description": "",
+        "theme": "core",
+        "ctf_timezone": "UTC",
+        "lang": "en",
+    }
+    session.post(
+        f"{cfg.ctfd_url}/setup",
+        data=data,
+        allow_redirects=False,
+        timeout=cfg.timeout,
+        verify=cfg.verify_tls,
+        headers={"Content-Type": "application/x-www-form-urlencoded"},
+    )
```

### Comment
![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

The `post_setup` function currently doesn't return the response from the POST request. Returning it would allow the calling function to inspect the result of the setup attempt. This can help provide better diagnostics and fail faster if something goes wrong, rather than waiting for the verification GET request to fail.

```suggestion
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
```

---

## Comment #4
**Author:** @gemini-code-assist
**File:** `ctfd_init.py`
**Line:** 118
**Created:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,152 @@
+#!/usr/bin/env python3
+"""CTFd initializer script.
+
+This script performs the first-boot setup for CTFd in a CSRF-aware manner.
+It is intentionally minimal and relies only on the Python standard library
+plus the `requests` package for HTTP interactions.
+
+The behaviour is driven by environment variables as documented in
+`DOCKER_SPEC.md`.
+"""
+from __future__ import annotations
+
+import json
+import logging
+import os
+import re
+import sys
+import time
+from dataclasses import dataclass
+from typing import Optional
+
+import requests
+
+LOG = logging.getLogger("ctfd_init")
+
+
+class SetupError(RuntimeError):
+    """Raised when the setup process ultimately fails."""
+
+
+@dataclass
+class Config:
+    ctfd_url: str
+    admin_username: Optional[str]
+    admin_email: Optional[str]
+    admin_password: Optional[str]
+    project_name: str = "CTF"
+    timeout: int = 10
+    attempts: int = 60
+    backoff: int = 2
+    verify_tls: bool = True
+
+    @classmethod
+    def from_env(cls) -> "Config":
+        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
+            value = os.environ.get(name, default)
+            return value
+
+        ctfd_url = os.environ.get("CTFD_URL")
+        if not ctfd_url:
+            raise SetupError("CTFD_URL is required")
+        return cls(
+            ctfd_url=ctfd_url.rstrip("/"),
+            admin_username=getenv("ADMIN_USERNAME"),
+            admin_email=getenv("ADMIN_EMAIL"),
+            admin_password=getenv("ADMIN_PASSWORD"),
+            project_name=getenv("PROJECT_NAME", "CTF"),
+            timeout=int(getenv("TIMEOUT_SECONDS", "10")),
+            attempts=int(getenv("RETRY_ATTEMPTS", "60")),
+            backoff=int(getenv("RETRY_BACKOFF_SECONDS", "2")),
+            verify_tls=getenv("VERIFY_TLS", "true").lower() == "true",
+        )
+
+
+def extract_nonce(html: str) -> Optional[str]:
+    """Extract CSRF nonce from setup HTML."""
+    match = re.search(r'name=[\"\']nonce[\"\']\s+value=[\"\']([^\"\']+)[\"\']', html)
+    if match:
+        return match.group(1)
+    return None
+
+
+def already_configured(response: requests.Response) -> bool:
+    """Return True if the /setup endpoint redirects away, meaning configured."""
+    return 300 <= response.status_code < 400
+
+
+def post_setup(session: requests.Session, cfg: Config, nonce: str) -> None:
+    data = {
+        "nonce": nonce,
+        "ctf_name": cfg.project_name,
+        "name": cfg.admin_username or "admin",
+        "email": cfg.admin_email or "admin@example.com",
+        "password": cfg.admin_password or "",
+        "ctf_description": "",
+        "theme": "core",
+        "ctf_timezone": "UTC",
+        "lang": "en",
+    }
+    session.post(
+        f"{cfg.ctfd_url}/setup",
+        data=data,
+        allow_redirects=False,
+        timeout=cfg.timeout,
+        verify=cfg.verify_tls,
+        headers={"Content-Type": "application/x-www-form-urlencoded"},
+    )
+
+
+def configure(cfg: Config) -> None:
+    session = requests.Session()
+    for attempt in range(1, cfg.attempts + 1):
+        start = time.time()
+        resp = session.get(
+            f"{cfg.ctfd_url}/setup",
+            allow_redirects=False,
+            timeout=cfg.timeout,
+            verify=cfg.verify_tls,
+        )
+        elapsed = int((time.time() - start) * 1000)
+        LOG.info(json.dumps({
+            "level": "info",
+            "attempt": attempt,
+            "status": resp.status_code,
+            "url": f"{cfg.ctfd_url}/setup",
+            "elapsed_ms": elapsed,
+            "msg": "GET /setup"
+        }))
```

### Comment
![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

The structured logs are missing the 'ts' (timestamp) field, which is specified as a requirement in `DOCKER_SPEC.md`. Adding a timestamp to all JSON log messages will improve observability. You'll need to add `import datetime` at the top of the file. Please apply this to all logging calls in the script for consistency.

```python
        LOG.info(json.dumps({
            "level": "info",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "attempt": attempt,
            "status": resp.status_code,
            "url": f"{cfg.ctfd_url}/setup",
            "elapsed_ms": elapsed,
            "msg": "GET /setup"
        }))
```

---

## Comment #5
**Author:** @gemini-code-assist
**File:** `ctfd_init.py`
**Line:** 124
**Created:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,152 @@
+#!/usr/bin/env python3
+"""CTFd initializer script.
+
+This script performs the first-boot setup for CTFd in a CSRF-aware manner.
+It is intentionally minimal and relies only on the Python standard library
+plus the `requests` package for HTTP interactions.
+
+The behaviour is driven by environment variables as documented in
+`DOCKER_SPEC.md`.
+"""
+from __future__ import annotations
+
+import json
+import logging
+import os
+import re
+import sys
+import time
+from dataclasses import dataclass
+from typing import Optional
+
+import requests
+
+LOG = logging.getLogger("ctfd_init")
+
+
+class SetupError(RuntimeError):
+    """Raised when the setup process ultimately fails."""
+
+
+@dataclass
+class Config:
+    ctfd_url: str
+    admin_username: Optional[str]
+    admin_email: Optional[str]
+    admin_password: Optional[str]
+    project_name: str = "CTF"
+    timeout: int = 10
+    attempts: int = 60
+    backoff: int = 2
+    verify_tls: bool = True
+
+    @classmethod
+    def from_env(cls) -> "Config":
+        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
+            value = os.environ.get(name, default)
+            return value
+
+        ctfd_url = os.environ.get("CTFD_URL")
+        if not ctfd_url:
+            raise SetupError("CTFD_URL is required")
+        return cls(
+            ctfd_url=ctfd_url.rstrip("/"),
+            admin_username=getenv("ADMIN_USERNAME"),
+            admin_email=getenv("ADMIN_EMAIL"),
+            admin_password=getenv("ADMIN_PASSWORD"),
+            project_name=getenv("PROJECT_NAME", "CTF"),
+            timeout=int(getenv("TIMEOUT_SECONDS", "10")),
+            attempts=int(getenv("RETRY_ATTEMPTS", "60")),
+            backoff=int(getenv("RETRY_BACKOFF_SECONDS", "2")),
+            verify_tls=getenv("VERIFY_TLS", "true").lower() == "true",
+        )
+
+
+def extract_nonce(html: str) -> Optional[str]:
+    """Extract CSRF nonce from setup HTML."""
+    match = re.search(r'name=[\"\']nonce[\"\']\s+value=[\"\']([^\"\']+)[\"\']', html)
+    if match:
+        return match.group(1)
+    return None
+
+
+def already_configured(response: requests.Response) -> bool:
+    """Return True if the /setup endpoint redirects away, meaning configured."""
+    return 300 <= response.status_code < 400
+
+
+def post_setup(session: requests.Session, cfg: Config, nonce: str) -> None:
+    data = {
+        "nonce": nonce,
+        "ctf_name": cfg.project_name,
+        "name": cfg.admin_username or "admin",
+        "email": cfg.admin_email or "admin@example.com",
+        "password": cfg.admin_password or "",
+        "ctf_description": "",
+        "theme": "core",
+        "ctf_timezone": "UTC",
+        "lang": "en",
+    }
+    session.post(
+        f"{cfg.ctfd_url}/setup",
+        data=data,
+        allow_redirects=False,
+        timeout=cfg.timeout,
+        verify=cfg.verify_tls,
+        headers={"Content-Type": "application/x-www-form-urlencoded"},
+    )
+
+
+def configure(cfg: Config) -> None:
+    session = requests.Session()
+    for attempt in range(1, cfg.attempts + 1):
+        start = time.time()
+        resp = session.get(
+            f"{cfg.ctfd_url}/setup",
+            allow_redirects=False,
+            timeout=cfg.timeout,
+            verify=cfg.verify_tls,
+        )
+        elapsed = int((time.time() - start) * 1000)
+        LOG.info(json.dumps({
+            "level": "info",
+            "attempt": attempt,
+            "status": resp.status_code,
+            "url": f"{cfg.ctfd_url}/setup",
+            "elapsed_ms": elapsed,
+            "msg": "GET /setup"
+        }))
+        if already_configured(resp):
+            LOG.info(json.dumps({"level": "info", "msg": "Already configured"}))
+            return
+        nonce = extract_nonce(resp.text)
+        if nonce and cfg.admin_password:
+            post_setup(session, cfg, nonce)
```

### Comment
![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

Following the change to have `post_setup` return the response, you should check it here. A successful setup POST request should result in a redirect (status code 3xx). If it doesn't, you can log a warning. While the subsequent GET for verification is the ultimate decider according to the spec, checking the POST response provides earlier feedback on failures.

```python
            post_resp = post_setup(session, cfg, nonce)
            if not 300 <= post_resp.status_code < 400:
                LOG.warning(json.dumps({
                    "level": "warning",
                    "msg": "POST to /setup did not result in a redirect",
                    "status": post_resp.status_code
                }))
```

---

## Comment #6
**Author:** @gemini-code-assist
**File:** `ctfd_init.py`
**Line:** 146
**Created:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,152 @@
+#!/usr/bin/env python3
+"""CTFd initializer script.
+
+This script performs the first-boot setup for CTFd in a CSRF-aware manner.
+It is intentionally minimal and relies only on the Python standard library
+plus the `requests` package for HTTP interactions.
+
+The behaviour is driven by environment variables as documented in
+`DOCKER_SPEC.md`.
+"""
+from __future__ import annotations
+
+import json
+import logging
+import os
+import re
+import sys
+import time
+from dataclasses import dataclass
+from typing import Optional
+
+import requests
+
+LOG = logging.getLogger("ctfd_init")
+
+
+class SetupError(RuntimeError):
+    """Raised when the setup process ultimately fails."""
+
+
+@dataclass
+class Config:
+    ctfd_url: str
+    admin_username: Optional[str]
+    admin_email: Optional[str]
+    admin_password: Optional[str]
+    project_name: str = "CTF"
+    timeout: int = 10
+    attempts: int = 60
+    backoff: int = 2
+    verify_tls: bool = True
+
+    @classmethod
+    def from_env(cls) -> "Config":
+        def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
+            value = os.environ.get(name, default)
+            return value
+
+        ctfd_url = os.environ.get("CTFD_URL")
+        if not ctfd_url:
+            raise SetupError("CTFD_URL is required")
+        return cls(
+            ctfd_url=ctfd_url.rstrip("/"),
+            admin_username=getenv("ADMIN_USERNAME"),
+            admin_email=getenv("ADMIN_EMAIL"),
+            admin_password=getenv("ADMIN_PASSWORD"),
+            project_name=getenv("PROJECT_NAME", "CTF"),
+            timeout=int(getenv("TIMEOUT_SECONDS", "10")),
+            attempts=int(getenv("RETRY_ATTEMPTS", "60")),
+            backoff=int(getenv("RETRY_BACKOFF_SECONDS", "2")),
+            verify_tls=getenv("VERIFY_TLS", "true").lower() == "true",
+        )
+
+
+def extract_nonce(html: str) -> Optional[str]:
+    """Extract CSRF nonce from setup HTML."""
+    match = re.search(r'name=[\"\']nonce[\"\']\s+value=[\"\']([^\"\']+)[\"\']', html)
+    if match:
+        return match.group(1)
+    return None
+
+
+def already_configured(response: requests.Response) -> bool:
+    """Return True if the /setup endpoint redirects away, meaning configured."""
+    return 300 <= response.status_code < 400
+
+
+def post_setup(session: requests.Session, cfg: Config, nonce: str) -> None:
+    data = {
+        "nonce": nonce,
+        "ctf_name": cfg.project_name,
+        "name": cfg.admin_username or "admin",
+        "email": cfg.admin_email or "admin@example.com",
+        "password": cfg.admin_password or "",
+        "ctf_description": "",
+        "theme": "core",
+        "ctf_timezone": "UTC",
+        "lang": "en",
+    }
+    session.post(
+        f"{cfg.ctfd_url}/setup",
+        data=data,
+        allow_redirects=False,
+        timeout=cfg.timeout,
+        verify=cfg.verify_tls,
+        headers={"Content-Type": "application/x-www-form-urlencoded"},
+    )
+
+
+def configure(cfg: Config) -> None:
+    session = requests.Session()
+    for attempt in range(1, cfg.attempts + 1):
+        start = time.time()
+        resp = session.get(
+            f"{cfg.ctfd_url}/setup",
+            allow_redirects=False,
+            timeout=cfg.timeout,
+            verify=cfg.verify_tls,
+        )
+        elapsed = int((time.time() - start) * 1000)
+        LOG.info(json.dumps({
+            "level": "info",
+            "attempt": attempt,
+            "status": resp.status_code,
+            "url": f"{cfg.ctfd_url}/setup",
+            "elapsed_ms": elapsed,
+            "msg": "GET /setup"
+        }))
+        if already_configured(resp):
+            LOG.info(json.dumps({"level": "info", "msg": "Already configured"}))
+            return
+        nonce = extract_nonce(resp.text)
+        if nonce and cfg.admin_password:
+            post_setup(session, cfg, nonce)
+            # verify
+            verify_resp = session.get(
+                f"{cfg.ctfd_url}/setup",
+                allow_redirects=False,
+                timeout=cfg.timeout,
+                verify=cfg.verify_tls,
+            )
+            if already_configured(verify_resp):
+                LOG.info(json.dumps({"level": "info", "msg": "Configured successfully"}))
+                return
+        time.sleep(cfg.backoff)
+    raise SetupError("setup not completed after retries")
+
+
+def main() -> int:
+    logging.basicConfig(level=logging.INFO, format="%(message)s")
+    try:
+        cfg = Config.from_env()
+        configure(cfg)
+    except SetupError as exc:
+        LOG.error(json.dumps({"level": "error", "msg": str(exc)}))
+        return 1
```

### Comment
![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

The `DOCKER_SPEC.md` file specifies distinct exit codes for different failure scenarios (e.g., 10 for unrecoverable error, 11 for nonce not found). The current implementation returns a generic '1' for all `SetupError` exceptions. To align better with the spec and provide more granular error information, consider modifying the `SetupError` exception to carry an exit code, and then return that code here.

---

## Comment #7
**Author:** @gemini-code-assist
**File:** `tests/test_init.py`
**Line:** 64
**Created:** 2025-08-26 20:15:05 UTC

### Code Context
```diff
@@ -0,0 +1,65 @@
+import requests
+import responses
+import pytest
+
+from ctfd_init import extract_nonce, already_configured, Config, configure
+
+
+def test_extract_nonce():
+    html = '<input type="hidden" name="nonce" value="abc123">'
+    assert extract_nonce(html) == "abc123"
+
+
+def test_already_configured_redirect():
+    resp = requests.Response()
+    resp.status_code = 302
+    assert already_configured(resp)
+
+
+def test_already_configured_ok():
+    resp = requests.Response()
+    resp.status_code = 200
+    assert not already_configured(resp)
+
+
+@responses.activate
+def test_configure_success():
+    responses.get(
+        "https://ctfd.example.com/setup",
+        status=200,
+        body='<input type="hidden" name="nonce" value="abc">',
+    )
+    responses.post(
+        "https://ctfd.example.com/setup",
+        status=302,
+        headers={"Location": "/"},
+    )
+    responses.get(
+        "https://ctfd.example.com/setup",
+        status=302,
+        headers={"Location": "/"},
+    )
+    cfg = Config(
+        ctfd_url="https://ctfd.example.com",
+        admin_username="admin",
+        admin_email="admin@example.com",
+        admin_password="secret",
+        attempts=1,
+        backoff=0,
+    )
+    configure(cfg)
+
+
+@responses.activate
+def test_configure_fail_after_retries():
+    responses.get("https://ctfd.example.com/setup", status=200, body="no nonce")
+    cfg = Config(
+        ctfd_url="https://ctfd.example.com",
+        admin_username="admin",
+        admin_email="admin@example.com",
+        admin_password="secret",
+        attempts=1,
+        backoff=0,
+    )
+    with pytest.raises(Exception):
```

### Comment
![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

It's a best practice in testing to catch specific exceptions rather than the generic `Exception`. The `configure` function is designed to raise `SetupError` on failure. Updating the test to expect `SetupError` will make it more precise. You'll need to import `SetupError` from `ctfd_init` at the top of the file.

```suggestion
    with pytest.raises(SetupError):
```

---
