# CTFd Initializer

A simple, idempotent, and CSRF-aware container to perform the first-boot setup for a [CTFd](https://ctfd.io/) instance. This tool is designed to run as an init/sidecar container in environments like ECS or Kubernetes, ensuring that CTFd is fully configured before it starts accepting traffic.

It is built to be minimal, secure, and configurable entirely through environment variables.

## Features

- **Idempotent**: Safely runs to completion without making changes if CTFd is already configured.
- **CSRF Aware**: Automatically fetches a valid CSRF nonce before submitting the setup form.
- **Configurable**: All settings are controlled via environment variables.
- **Retry Logic**: Includes exponential backoff with jitter to reliably wait for the CTFd service to be ready.
- **Minimal & Secure**: Built on a distroless, non-root base image with a minimal dependency footprint.
- **Structured Logging**: Outputs JSON logs for easy parsing and monitoring.

## Quick Start: Running with Docker

To use this initializer, you can build the Docker image and run it, pointing it at your CTFd instance.

1.  **Build the Docker Image:**
    ```sh
    docker build -t ctfd-initializer .
    ```

2.  **Run the Initializer:**
    Set the required environment variables and run the container. It will exit once CTFd is configured.

    ```sh
    docker run --rm --env-file .env ctfd-initializer
    ```
    *(See the Configuration section for details on creating a `.env` file)*

## Configuration

The initializer is configured using the following environment variables.

| Variable | Description | Required | Default |
| :--- | :--- | :--- | :--- |
| `CTFD_URL` | The base URL of the CTFd instance (e.g., `http://localhost:8000`). | **Yes** | - |
| `ADMIN_USERNAME` | The desired username for the admin account. | **Yes** | - |
| `ADMIN_EMAIL` | The desired email for the admin account. | **Yes** | - |
| `ADMIN_PASSWORD` | The admin password. If unset, the script only polls for readiness. | No | - |
| `PROJECT_NAME` | The name of the CTF project. | No | `"CTF"` |
| `CTF_DESCRIPTION` | A description for the CTF. | No | `""` |
| `CTF_THEME` | The theme to use for the CTF. | No | `"core"` |
| `CTF_TIMEZONE` | The timezone for the CTF. | No | `"UTC"` |
| `CTF_LANG` | The language for the CTF. | No | `"en"` |
| `TIMEOUT_SECONDS` | Timeout in seconds for individual HTTP requests. | No | `10` |
| `RETRY_ATTEMPTS` | Maximum number of attempts to configure CTFd. | No | `60` |
| `RETRY_BACKOFF_SECONDS` | The initial backoff duration in seconds for retries. | No | `2` |
| `VERIFY_TLS` | Set to `false` to disable TLS certificate verification. | No | `true` |
| `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` | Standard proxy configuration (handled automatically by `requests`). | No | - |

### Example `.env` file:
```env
CTFD_URL=http://localhost:8000
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=password
PROJECT_NAME="My Awesome CTF"
```

## Local Development & Testing

You can run the Python script locally for development and testing purposes. This project uses `uv` for fast dependency management.

1.  **Install `uv`:**
    Follow the official instructions at [astral.sh/uv](https://astral.sh/uv).

2.  **Create a Virtual Environment:**
    ```sh
    uv venv
    ```

3.  **Activate the Environment:**
    ```sh
    source .venv/bin/activate
    ```

4.  **Install Dependencies:**
    ```sh
    uv pip install -r requirements.txt
    ```

5.  **Run a Local CTFd Instance:**
    For testing, you can easily spin up a CTFd container.
    ```sh
    docker run -p 8000:8000 -itd --name ctfd-test ctfd/ctfd
    ```

6.  **Run the Script:**
    Create a `.env` file as shown above and run the script. It will configure the running Docker container.
    ```sh
    # For local execution, ensure the environment variables from your .env
    # file are loaded into your shell. A robust way to do this, which handles
    # special characters, is to source the file:
    #
    # set -a; source .env; set +a
    #
    # After loading the variables, run the script:
    python ctfd_init.py
    ```

7.  **Clean Up:**
    When you are done, you can stop and remove the test container.
    ```sh
    docker stop ctfd-test
    docker rm ctfd-test
    ```
