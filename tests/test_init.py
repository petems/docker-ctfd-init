import requests
import responses
import pytest

from ctfd_init import extract_nonce, already_configured, Config, configure


def test_extract_nonce():
    html = '<input type="hidden" name="nonce" value="abc123">'
    assert extract_nonce(html) == "abc123"


def test_already_configured_redirect():
    resp = requests.Response()
    resp.status_code = 302
    assert already_configured(resp)


def test_already_configured_ok():
    resp = requests.Response()
    resp.status_code = 200
    assert not already_configured(resp)


@responses.activate
def test_configure_success():
    responses.get(
        "https://ctfd.example.com/setup",
        status=200,
        body='<input type="hidden" name="nonce" value="abc">',
    )
    responses.post(
        "https://ctfd.example.com/setup",
        status=302,
        headers={"Location": "/"},
    )
    responses.get(
        "https://ctfd.example.com/setup",
        status=302,
        headers={"Location": "/"},
    )
    cfg = Config(
        ctfd_url="https://ctfd.example.com",
        admin_username="admin",
        admin_email="admin@example.com",
        admin_password="secret",
        attempts=1,
        backoff=0,
    )
    configure(cfg)


@responses.activate
def test_configure_fail_after_retries():
    responses.get("https://ctfd.example.com/setup", status=200, body="no nonce")
    cfg = Config(
        ctfd_url="https://ctfd.example.com",
        admin_username="admin",
        admin_email="admin@example.com",
        admin_password="secret",
        attempts=1,
        backoff=0,
    )
    with pytest.raises(Exception):
        configure(cfg)
