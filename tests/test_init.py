import os
import sys
import json
import pytest
import responses
import importlib
from unittest.mock import patch

# Add the root directory to the path so we can import ctfd_init from the parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# The module we are testing
import ctfd_init

# --- Test Constants ---
BASE_URL = "http://ctfd.test"
SETUP_URL = f"{BASE_URL}/setup"
API_CONFIG_URL = f"{BASE_URL}/api/v1/configs"
NONCE = "a1b2c3d4e5f6"
SUCCESS_SETUP_HTML = f'<html><body><input type="hidden" name="nonce" value="{NONCE}"></body></html>'
NO_NONCE_HTML = '<html><body><p>No nonce here</p></body></html>'

# --- Fixtures ---

@pytest.fixture
def mock_env(monkeypatch):
    """A fixture to mock environment variables and reload the ctfd_init module."""
    def _mock_env(env_vars):
        # Set all provided env vars
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)
        # Unset others that might be lingering from other tests
        for k in ["CTFD_URL", "ADMIN_USERNAME", "ADMIN_EMAIL", "ADMIN_PASSWORD", "TIMEOUT_SECONDS", "RETRY_ATTEMPTS", "RETRY_BACKOFF_SECONDS"]:
            if k not in env_vars:
                monkeypatch.delenv(k, raising=False)

        # Reload the module to apply the new environment variables.
        importlib.reload(ctfd_init)
    return _mock_env

# --- Test Cases ---

@responses.activate
def test_full_success_flow(mock_env):
    """Test the ideal scenario: not configured -> get nonce -> post setup -> confirm -> exit 0."""
    mock_env({
        "CTFD_URL": BASE_URL,
        "ADMIN_USERNAME": "admin",
        "ADMIN_EMAIL": "admin@test.com",
        "ADMIN_PASSWORD": "password"
    })

    # 1. First check: CTFd is not configured.
    responses.add(responses.GET, SETUP_URL, body=SUCCESS_SETUP_HTML, status=200)
    responses.add(responses.GET, API_CONFIG_URL, status=200)
    # 2. get_csrf_nonce call
    responses.add(responses.GET, SETUP_URL, body=SUCCESS_SETUP_HTML, status=200)
    # 3. POST to /setup is successful and redirects.
    responses.add(responses.POST, SETUP_URL, status=302, headers={'Location': BASE_URL})
    # 4. Final confirmation check sees the redirect.
    responses.add(responses.GET, SETUP_URL, status=302)

    with pytest.raises(SystemExit) as e:
        ctfd_init.main()

    assert e.value.code == 0
    assert len(responses.calls) == 5
    assert responses.calls[3].request.body == f"nonce={NONCE}&ctf_name=CTF&name=admin&email=admin%40test.com&password=password&ctf_description=&theme=core&ctf_timezone=UTC&lang=en"

@responses.activate
def test_already_configured_by_redirect(mock_env):
    """Test idempotency: if /setup redirects, script exits 0 immediately."""
    mock_env({"CTFD_URL": BASE_URL})
    responses.add(responses.GET, SETUP_URL, status=302)

    with pytest.raises(SystemExit) as e:
        ctfd_init.main()
    assert e.value.code == 0
    assert len(responses.calls) == 1

@responses.activate
def test_polling_flow_succeeds(mock_env):
    """Test polling behavior: ADMIN_PASSWORD is not set, script polls and exits when configured."""
    mock_env({
        "CTFD_URL": BASE_URL,
        "RETRY_BACKOFF_SECONDS": "0" # Use integer for speed
    })

    # First check: not configured
    responses.add(responses.GET, SETUP_URL, status=200)
    responses.add(responses.GET, API_CONFIG_URL, status=200)
    # Second check: configured
    responses.add(responses.GET, SETUP_URL, status=302)

    with patch('time.sleep') as mock_sleep:
        with pytest.raises(SystemExit) as e:
            ctfd_init.main()

    assert e.value.code == 0
    mock_sleep.assert_called_once()
    assert len(responses.calls) == 3

@responses.activate
def test_full_failure_after_retries(mock_env):
    """Test exit code 12 after all retries are exhausted."""
    mock_env({
        "CTFD_URL": BASE_URL,
        "ADMIN_PASSWORD": "password",
        "ADMIN_USERNAME": "admin",
        "ADMIN_EMAIL": "admin@test.com",
        "RETRY_ATTEMPTS": "3",
        "RETRY_BACKOFF_SECONDS": "0"
    })

    # Mock /setup to always indicate it's not configured and no nonce is found
    responses.add(responses.GET, SETUP_URL, body=NO_NONCE_HTML, status=200)
    responses.add(responses.GET, API_CONFIG_URL, status=200)

    with patch('time.sleep'):
        with pytest.raises(SystemExit) as e:
            ctfd_init.main()

    assert e.value.code == 12
    # 3 attempts * (2 checks for configured + 1 for nonce) = 9 calls
    assert len(responses.calls) == 9

def test_config_no_url_exits(mock_env, capsys):
    """Test that the script exits with code 10 if CTFD_URL is not set."""
    mock_env({})
    with pytest.raises(SystemExit) as e:
        ctfd_init.main()

    assert e.value.code == 10
    captured = capsys.readouterr()
    assert "CTFD_URL environment variable is not set" in json.loads(captured.out)["msg"]

def test_config_empty_password_exits(mock_env, capsys):
    """Test that the script exits with code 10 if ADMIN_PASSWORD is an empty string."""
    mock_env({"CTFD_URL": BASE_URL, "ADMIN_PASSWORD": ""})

    with pytest.raises(SystemExit) as e:
        ctfd_init.main()

    assert e.value.code == 10
    captured = capsys.readouterr()
    assert "ADMIN_PASSWORD is set but empty" in json.loads(captured.out)["msg"]

def test_config_invalid_numeric_exits(mock_env, capsys):
    """Test that the script exits with code 10 if a numeric env var is invalid."""
    with pytest.raises(SystemExit) as e:
        mock_env({"CTFD_URL": BASE_URL, "TIMEOUT_SECONDS": "not-a-number"})

    assert e.value.code == 10
    captured = capsys.readouterr()
    assert "must be integers" in json.loads(captured.err)["msg"]

@responses.activate
def test_csrf_nonce_not_found(mock_env, capsys):
    """Test that get_csrf_nonce returns None and logs an error if nonce is not found."""
    mock_env({"CTFD_URL": BASE_URL})
    responses.add(responses.GET, SETUP_URL, body=NO_NONCE_HTML, status=200)

    import requests
    session = requests.Session()
    nonce = ctfd_init.get_csrf_nonce(session, BASE_URL)

    assert nonce is None
    captured = capsys.readouterr()
    log_output = json.loads(captured.out)
    assert log_output["msg"] == "Could not find CSRF nonce in setup page."
    assert log_output["level"] == "ERROR"
