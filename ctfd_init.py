import os
import sys
import time
import json
import logging
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from urllib.parse import urlparse

# --- Configuration ---
CTFD_URL = os.getenv("CTFD_URL")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
PROJECT_NAME = os.getenv("PROJECT_NAME", "CTF")
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", 10))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", 60))
RETRY_BACKOFF_SECONDS = int(os.getenv("RETRY_BACKOFF_SECONDS", 2))
VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() == "true"

# --- Logging ---
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "ts": self.formatTime(record, self.datefmt),
            "msg": record.getMessage(),
        }
        if hasattr(record, 'extra_info'):
            log_record.update(record.extra_info)

        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    # Set a custom attribute on the record to avoid conflicts
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    # Silence noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    return logger

log = setup_logging()

def log_with_context(level, msg, **kwargs):
    """Helper to log with extra context."""
    getattr(log, level)(msg, extra={'extra_info': kwargs})


# --- Main Logic ---
def check_if_configured(session, url):
    """Check if CTFd is already configured."""
    setup_url = f"{url}/setup"
    try:
        start_time = time.monotonic()
        resp = session.get(setup_url, allow_redirects=False, timeout=TIMEOUT_SECONDS)
        elapsed_ms = (time.monotonic() - start_time) * 1000

        log_context = {"url": setup_url, "status": resp.status_code, "elapsed_ms": int(elapsed_ms)}

        # If we get a redirect, it means setup is complete.
        if resp.status_code >= 300 and resp.status_code < 400:
            log_with_context("info", "CTFd is already configured (redirect on /setup).", **log_context)
            return True

        # Another way to check: /api/v1/configs requires auth if configured
        api_url = f"{url}/api/v1/configs"
        start_time_api = time.monotonic()
        api_resp = session.get(api_url, timeout=TIMEOUT_SECONDS)
        elapsed_ms_api = (time.monotonic() - start_time_api) * 1000
        log_context_api = {"url": api_url, "status": api_resp.status_code, "elapsed_ms": int(elapsed_ms_api)}
        if api_resp.status_code in [401, 403]:
            log_with_context("info", "CTFd is already configured (API requires auth).", **log_context_api)
            return True

        log_with_context("info", "CTFd is not configured yet.", **log_context)
        return False

    except RequestException as e:
        log_with_context("warning", "Failed to connect to CTFd to check configuration.", url=setup_url, error=str(e))
        return False

def get_csrf_nonce(session, url):
    """Fetch the CSRF nonce from the setup page."""
    setup_url = f"{url}/setup"
    try:
        resp = session.get(setup_url, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        nonce_tag = soup.find("input", {"name": "nonce"})
        if nonce_tag and nonce_tag.get("value"):
            return nonce_tag["value"]
        log_with_context("error", "Could not find CSRF nonce in setup page.", url=setup_url)
        return None
    except RequestException as e:
        log_with_context("error", "Failed to fetch setup page for CSRF nonce.", url=setup_url, error=str(e))
        return None

def perform_setup(session, url, nonce):
    """Post the setup form to CTFd."""
    setup_url = f"{url}/setup"
    form_data = {
        "nonce": nonce,
        "ctf_name": PROJECT_NAME,
        "name": ADMIN_USERNAME,
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "ctf_description": "",
        "theme": "core",
        "ctf_timezone": "UTC",
        "lang": "en",
    }

    # Redact password for logging
    log_form_data = form_data.copy()
    if "password" in log_form_data:
        log_form_data["password"] = "[REDACTED]"

    log_with_context("info", "Posting setup form...", url=setup_url, data=log_form_data)

    try:
        start_time = time.monotonic()
        resp = session.post(
            setup_url,
            data=form_data,
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False
        )
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log_context = {"url": setup_url, "status": resp.status_code, "elapsed_ms": int(elapsed_ms)}

        if resp.status_code >= 300 and resp.status_code < 400:
            log_with_context("info", "Setup POST successful (got redirect).", **log_context)
            return True
        else:
            log_with_context("error", "Setup POST failed.", **log_context)
            # Log a snippet of the response if possible, avoiding full HTML dumps
            log.error(f"Response snippet: {resp.text[:200]}")
            return False

    except RequestException as e:
        log_with_context("error", "Failed to post setup form.", url=setup_url, error=str(e))
        return False

def main():
    """Main execution flow."""
    if not CTFD_URL:
        log_with_context("error", "CTFD_URL environment variable is not set. Exiting.")
        sys.exit(10)

    session = requests.Session()
    session.verify = VERIFY_TLS
    # Support proxy settings from environment
    session.proxies = {
        'http': os.environ.get('HTTP_PROXY'),
        'https': os.environ.get('HTTPS_PROXY'),
    }
    if os.environ.get('NO_PROXY'):
        if urlparse(CTFD_URL).hostname in os.environ['NO_PROXY'].split(','):
            session.proxies = {}


    for attempt in range(1, RETRY_ATTEMPTS + 1):
        log_context = {"attempt": f"{attempt}/{RETRY_ATTEMPTS}"}
        log_with_context("info", "Starting setup check...", **log_context)

        if check_if_configured(session, CTFD_URL):
            sys.exit(0)

        if not ADMIN_PASSWORD:
            log_with_context("info", "ADMIN_PASSWORD not set. Polling until configured or retries exhausted.", **log_context)
        else:
            if not all([ADMIN_USERNAME, ADMIN_EMAIL]):
                log_with_context("error", "ADMIN_USERNAME and ADMIN_EMAIL are required when ADMIN_PASSWORD is set. Exiting.")
                sys.exit(10)

            nonce = get_csrf_nonce(session, CTFD_URL)
            if not nonce:
                log_with_context("warning", "Could not get CSRF nonce. Retrying...", **log_context)
            else:
                if perform_setup(session, CTFD_URL, nonce):
                    time.sleep(1) # Give a moment for the app to process
                    if check_if_configured(session, CTFD_URL):
                        log_with_context("info", "Configuration confirmed successfully.")
                        sys.exit(0)
                    else:
                        log_with_context("error", "Setup seemed successful, but confirmation check failed. Retrying...", **log_context)

        backoff = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
        # Add jitter
        backoff = backoff * (0.8 + 0.4 * os.urandom(1)[0] / 255)
        log_with_context("info", f"Retrying in {backoff:.1f} seconds...", **log_context)
        time.sleep(backoff)

    log_with_context("error", "Failed to configure CTFd after all attempts. Exiting.")
    sys.exit(12)

if __name__ == "__main__":
    main()
