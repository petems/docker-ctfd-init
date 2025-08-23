#!/bin/bash
#
# Acceptance Test for the CTFd Initializer
#
# This script performs a live, end-to-end test:
# 1. Builds the initializer Docker image.
# 2. Starts a fresh ctfd/ctfd container.
# 3. Waits for the CTFd container to become responsive.
# 4. Runs the initializer container to configure CTFd.
# 5. Verifies that the setup was successful by checking for a redirect.
# 6. Runs the initializer again to test for idempotency.
# 7. Cleans up all containers.

set -eo pipefail # Exit on error and pipe failure

# --- Configuration ---
IMG_NAME="ctfd-initializer:acceptance-test"
CTFD_CONTAINER_NAME="ctfd-acceptance-test-instance"
CTFD_URL="http://localhost:8000"

# --- Cleanup Function ---
# This function is called on EXIT, ensuring containers are always cleaned up.
cleanup() {
    echo "--- Cleaning up containers ---"
    sudo docker stop "$CTFD_CONTAINER_NAME" &>/dev/null || true
    sudo docker rm "$CTFD_CONTAINER_NAME" &>/dev/null || true
    echo "--- Cleanup complete ---"
}
trap cleanup EXIT

# --- Main Test Logic ---

echo "--- 1. Building Initializer Docker Image ---"
sudo docker build -t "$IMG_NAME" .

echo "--- 2. Starting CTFd Container ---"
sudo docker run -d --name "$CTFD_CONTAINER_NAME" -p 8000:8000 ctfd/ctfd:latest

echo "--- 3. Waiting for CTFd to be ready ---"
# Poll the CTFd container until its /setup page returns a 200 OK.
# Timeout after 60 seconds to prevent the script from running indefinitely.
timeout 60s bash -c \
    'until curl -s -f -o /dev/null "http://localhost:8000/setup"; do \
        echo "Waiting for CTFd to be online..."; \
        sleep 5; \
    done'
echo "--- CTFd is up! ---"

echo "--- 4. Running Initializer (First Pass) ---"
# We use --network container:... to allow the initializer to reach CTFd at localhost.
sudo docker run --rm \
    --network "container:${CTFD_CONTAINER_NAME}" \
    -e CTFD_URL="$CTFD_URL" \
    -e ADMIN_USERNAME="admin" \
    -e ADMIN_EMAIL="admin@example.com" \
    -e ADMIN_PASSWORD="password" \
    -e RETRY_ATTEMPTS=10 \
    -e RETRY_BACKOFF_SECONDS=1 \
    "$IMG_NAME"

echo "--- 5. Verifying Setup Completion ---"
# After a successful setup, a GET request to /setup should result in a 302 redirect.
status_code=$(curl -s -o /dev/null -w "%{http_code}" "$CTFD_URL/setup")
if [ "$status_code" -ne 302 ]; then
    echo "Error: Expected status code 302 from /setup, but got $status_code"
    exit 1
fi
echo "--- Verification successful: /setup redirects as expected. ---"

echo "--- 6. Running Initializer (Second Pass for Idempotency) ---"
# Running the initializer again should have no effect and exit cleanly.
sudo docker run --rm \
    --network "container:${CTFD_CONTAINER_NAME}" \
    -e CTFD_URL="$CTFD_URL" \
    -e ADMIN_USERNAME="admin" \
    -e ADMIN_EMAIL="admin@example.com" \
    -e ADMIN_PASSWORD="password" \
    "$IMG_NAME"

echo "--- Idempotency test successful. ---"

echo ""
echo "✅ Acceptance Test Passed!"
echo ""
