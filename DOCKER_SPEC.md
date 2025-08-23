## CTFd Initializer Container (CSRF-aware) – Design Spec

### Goals
- Perform CTFd first-boot setup non-interactively using a CSRF-aware POST to `/setup`.
- Be idempotent: safe to run repeatedly; do nothing if already configured.
- Be minimal and secure: tiny image, non-root, pinned deps, clear logging.
- Work cleanly as an ECS/Fargate sidecar/init-like container, exiting when setup is complete.

### Inputs (environment variables)
- CTFD_URL: Base URL (e.g. https://ctfd.example.com). Required.
- ADMIN_USERNAME: Admin display name. Required if auto-creating.
- ADMIN_EMAIL: Admin email. Required if auto-creating.
- ADMIN_PASSWORD: Admin password. If empty, do not create; only detect configured.
- PROJECT_NAME: Name to set for `ctf_name`. Optional; default "CTF".
- TIMEOUT_SECONDS: Per-request timeout. Default 10.
- RETRY_ATTEMPTS: Max attempts to detect/complete setup. Default 60.
- RETRY_BACKOFF_SECONDS: Initial backoff. Default 2 (exponential backoff recommended).
- VERIFY_TLS: true/false. Default true. Set false only for testing.
- HTTP_PROXY/HTTPS_PROXY/NO_PROXY: Standard proxy envs supported.

### Success criteria (idempotency)
- “Already configured”: GET `/setup` does 3xx redirect away from `/setup` (no redirect follow), or subsequent GET `/api/v1/configs` requires auth (401/403) or non-/setup redirect.
- “Setup completed now”: After POSTing the CSRF form, the next GET `/setup` returns a 3xx redirect away from `/setup`.

### Flow (CSRF-aware)
1) GET `/setup` without following redirects, capturing cookies.
2) Parse CSRF nonce from the HTML response: hidden input `name="nonce" value="..."`.
3) If `ADMIN_PASSWORD` is empty: only detect configured (step 1) and exit 0 when configured; otherwise keep polling until configured or retries exhausted.
4) If `ADMIN_PASSWORD` is provided: POST `application/x-www-form-urlencoded` to `/setup` with fields:
   - nonce, ctf_name, name (admin display name), email, password
   - Optional: ctf_description, theme ("core"), ctf_timezone ("UTC"), lang ("en")
5) Confirm configured via step 1 logic, then exit 0. On exhaustion, exit non-zero.

### Language recommendation
- Primary: Go (static binary)
  - Pros: single static binary; tiny distroless image; fast start; minimal CVE surface; no runtime package management churn.
  - Cons: slightly more code to manage cookies/CSRF parsing (use `net/http`, `html`, or a small HTML tokenizer).
- Alternative: Python 3
  - Pros: rapid development; good HTTP ergonomics.
  - Cons: larger image; dependency CVE churn; needs cert bundle handling; must pin deps.

Recommendation: Go for production-grade minimalism; Python acceptable for speed-of-iteration POC.

### Minimal image and security posture
- Image base:
  - Go: `gcr.io/distroless/static:nonroot` (includes CA certs) or `cgr.dev/chainguard/static`.
  - Python: `python:3.12-alpine` for build → final on `gcr.io/distroless/python3` with vendorized deps if required.
- Run as non-root (UID/GID 65532). No shell in final image.
- Read-only root filesystem; no write except optional emptyDir `/tmp`.
- Drop all capabilities (default in Fargate), no NET_RAW.
- Pin exact versions; reproducible builds.
- Supply SBOM and signatures (SLSA/Cosign) in CI; scan with Trivy/Grype.

### Logging
- Write to stdout only.
- Structured JSON logs with keys: level, ts, msg, attempt, url, status, elapsed_ms.
- Redact secrets (`ADMIN_PASSWORD`) in all logs.
- On failure, print a short diagnostic summary with last HTTP codes and minimal response snippets (no HTML dumps).

### Operational behavior
- Exit codes:
  - 0: already configured or configured successfully.
  - 10: unrecoverable HTTP/TLS/parse error.
  - 11: CSRF nonce not found after RETRY_ATTEMPTS.
  - 12: setup POST failed after RETRY_ATTEMPTS.
- Timeouts/retries: exponential backoff with jitter. Abort on context timeout.
- TLS: verify by default; allow `VERIFY_TLS=false` for test only.
- Idempotent: If setup already done, finish immediately (no changes).

### ECS/Fargate usage
- Run alongside CTFd task as a sidecar; not essential.
- Health-gate the main container (or ALB target group) on a sentinel check if desired; or rely solely on ALB `/setup` redirect health.
- Env wiring via task definition; do not mount secrets in logs.

### Example Go implementation sketch
- HTTP client with cookie jar; redirect-disabled transport.
- GET `/setup` → parse nonce (regex: `name=[\"']nonce[\"']\s+value=[\"']([^\"']+)`).
- POST form with nonce and fields using the same client (cookies preserved).
- Confirm via subsequent GET `/setup` (expect 3xx) before exiting 0.

### Example minimal container (Go)
```
# build stage
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "-s -w" -o /out/ctfd-init ./cmd/ctfd-init

# run stage
FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/ctfd-init /ctfd-init
USER nonroot:nonroot
ENTRYPOINT ["/ctfd-init"]
```

### Example minimal container (Python)
```
FROM python:3.12-alpine AS base
RUN apk add --no-cache ca-certificates && update-ca-certificates
WORKDIR /app
COPY init.py /app/init.py
# Optional: pip install requests==2.32.3 (pin), but stdlib urllib works
USER 65532:65532
ENTRYPOINT ["python","/app/init.py"]
```

### Testing
- Local dry-run: point `CTFD_URL` to a dev instance; run with `ADMIN_PASSWORD` and ensure it exits 0 and subsequent `/setup` redirects.
- Negative tests: invalid URL, bad TLS, missing nonce → proper exit codes.
- Idempotency: run twice; second run should detect configured and exit 0 quickly.

### Maintenance
- Pin and periodically update base image digests.
- Automate vulnerability scans and fail PRs on high/critical issues.
- Keep the CSRF selector tolerant to minor HTML changes; prefer robust token search over brittle DOM assumptions.

### Non-goals
- Direct SQL bootstrapping (brittle across versions, risky).
- Baking credentials into the image.


