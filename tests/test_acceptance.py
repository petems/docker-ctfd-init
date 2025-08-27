#!/usr/bin/env python3
"""Acceptance tests that run against a real CTFd instance."""

import os
import logging
import sys
import threading
import time
from contextlib import contextmanager

import docker
import pytest
import requests

from ctfd_init import Config, configure


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


_LOG = logging.getLogger("acceptance")


def _print(msg: str) -> None:
    """Emit test progress via logging so pytest streams it (log_cli)."""
    _LOG.info(msg)


def _stream_container_logs(container: docker.models.containers.Container, stop: threading.Event):
    """Continuously stream Docker logs until stop is set or container exits."""
    try:
        # Only stream new logs
        since = int(time.time())
        for chunk in container.logs(stream=True, follow=True, since=since):
            if stop.is_set():
                break
            try:
                line = chunk.decode("utf-8", errors="replace").rstrip()
            except Exception:
                line = str(chunk).rstrip()
            _print(f"[ctfd] {line}")
    except Exception as e:
        _print(f"[ctfd] log streaming stopped: {e}")


class DockerError(Exception):
    """Raised when Docker operations fail."""
    pass


def is_docker_available():
    """Check if Docker is available and running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _ctfd_image_default() -> str:
    """Return the CTFd image reference to use for acceptance tests.

    Respects env var `CTFD_IMAGE` and defaults to `ctfd/ctfd:latest`.
    """
    return os.environ.get("CTFD_IMAGE", "ctfd/ctfd:latest").strip()


@contextmanager
def ctfd_container(port=18000, container_name="ctfd-acceptance-test"):
    """Context manager that starts and cleans up a CTFd container."""
    client = docker.from_env()
    container = None
    log_thread = None
    stop_logs = threading.Event()
    
    try:
        # Clean up any existing container with the same name
        try:
            existing = client.containers.get(container_name)
            existing.stop(timeout=10)
            existing.remove()
        except docker.errors.NotFound:
            pass
        
        _print(f"Starting CTFd container '{container_name}' on port {port}...")
        # Start CTFd container
        image = _ctfd_image_default()
        container = client.containers.run(
            image,
            name=container_name,
            ports={'8000/tcp': port},
            detach=True,
        )
        _print(
            f"Container started: id={container.short_id}. Image={image}. "
            f"Streaming logs: {_env_truthy('STREAM_DOCKER_LOGS', '1')}"
        )

        # Optionally stream logs for visibility
        if _env_truthy("STREAM_DOCKER_LOGS", "1"):
            log_thread = threading.Thread(
                target=_stream_container_logs, args=(container, stop_logs), daemon=True
            )
            log_thread.start()
        
        # Readiness: poll HTTP endpoint instead of container healthcheck
        ctfd_url = f"http://localhost:{port}"
        _print(f"Probing {ctfd_url}/setup for readiness (HTTP polling)...")
        max_wait = 180  # seconds
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < max_wait:
            attempt += 1
            try:
                response = requests.get(f"{ctfd_url}/setup", timeout=5)
                if response.status_code == 200:
                    _print(f"/setup returned 200 (attempt {attempt}). Ready to configure.")
                    break
                else:
                    _print(f"/setup returned {response.status_code} (attempt {attempt}).")
            except requests.RequestException as e:
                _print(f"/setup not ready yet (attempt {attempt}): {e}")
            time.sleep(2)
        else:
            logs = container.logs().decode('utf-8', errors='replace')
            raise DockerError(f"CTFd setup endpoint not accessible after timeout. Logs:\n{logs}")
        
        yield ctfd_url
        
    finally:
        # Clean up container
        if container:
            try:
                _print("Stopping container...")
                container.stop(timeout=10)
                container.remove()
            except Exception as e:
                print(f"Warning: Failed to clean up container: {e}")
        # Stop log streaming last
        stop_logs.set()
        if log_thread and log_thread.is_alive():
            try:
                log_thread.join(timeout=3)
            except Exception:
                pass


@pytest.mark.acceptance
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_ctfd_initialization_success():
    """Test successful CTFd initialization with a real container."""
    with ctfd_container() as ctfd_url:
        # Configure the initializer
        config = Config(
            ctfd_url=ctfd_url,
            admin_username="admin",
            admin_email="admin@example.com", 
            admin_password="supersecret123",
            project_name="Test CTF",
            attempts=30,  # More attempts for acceptance test
            backoff=1,    # Shorter backoff for faster tests
            max_backoff=8,
        )
        
        # Run the initialization
        configure(config)
        
        # Verify the setup was successful by checking that /setup redirects
        response = requests.get(f"{ctfd_url}/setup", allow_redirects=False)
        assert response.status_code == 302, "Setup should redirect after successful configuration"
        
        # Verify we can access the main page
        response = requests.get(ctfd_url, timeout=10)
        assert response.status_code == 200, "Main page should be accessible"
        assert "Test CTF" in response.text, "Project name should appear on the page"


@pytest.mark.acceptance
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
def test_ctfd_already_configured_detection():
    """Test that the script correctly detects already configured CTFd instances."""
    with ctfd_container() as ctfd_url:
        # First initialization
        config = Config(
            ctfd_url=ctfd_url,
            admin_username="admin",
            admin_email="admin@example.com",
            admin_password="supersecret123",
            project_name="Test CTF",
            attempts=30,
            backoff=1,
            max_backoff=8,
        )
        
        configure(config)
        
        # Second initialization should detect it's already configured
        # This time without password (as per the real-world use case)
        config_detect = Config(
            ctfd_url=ctfd_url,
            admin_username=None,
            admin_email=None,
            admin_password=None,
            attempts=5,
            backoff=1,
            max_backoff=8,
        )
        
        # This should succeed quickly without attempting to configure
        configure(config_detect)
        
        # Verify it's still working
        response = requests.get(f"{ctfd_url}/setup", allow_redirects=False)
        assert response.status_code == 302, "Setup should still redirect"


@pytest.mark.acceptance
@pytest.mark.skipif(not is_docker_available(), reason="Docker not available") 
def test_ctfd_initialization_with_custom_settings():
    """Test CTFd initialization with custom project name and settings."""
    with ctfd_container() as ctfd_url:
        config = Config(
            ctfd_url=ctfd_url,
            admin_username="ctfadmin",
            admin_email="ctf@security.test",
            admin_password="ComplexPassword123!",
            project_name="Security Challenge 2024",
            attempts=30,
            backoff=1,
            max_backoff=8,
        )
        
        configure(config)
        
        # Verify custom project name appears
        response = requests.get(ctfd_url, timeout=10)
        assert response.status_code == 200
        assert "Security Challenge 2024" in response.text


if __name__ == "__main__":
    # Allow running acceptance tests directly
    pytest.main([__file__, "-v"])
