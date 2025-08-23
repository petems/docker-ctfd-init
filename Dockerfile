# ---- Build Stage ----
# Use a slim, Debian-based image for building the venv. This aligns with the debian-based distroless image.
FROM python:3.12-slim AS builder

# Install uv, the fast Python package installer
RUN pip install uv

# Set up the application directory
WORKDIR /app

# Create a virtual environment using uv
# This isolates dependencies and makes the final image cleaner
RUN uv venv /opt/venv

# Copy requirements and install dependencies into the venv
COPY requirements.txt .
# Using the venv's uv binary to install packages
RUN /opt/venv/bin/uv pip install --no-cache-dir -r requirements.txt

# Copy the application script into the build stage
COPY ctfd_init.py .


# ---- Final Stage ----
# Use a distroless image for a minimal and secure final image.
# It contains only the Python interpreter, its dependencies, and our app.
FROM gcr.io/distroless/python3-debian12

# Set the working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application script
COPY --from=builder /app/ctfd_init.py .

# Set a non-root user for security. UID 65532 is standard for 'nonroot'.
# The distroless image has this user pre-configured.
USER 65532:65532

# Set the entrypoint to use the Python from our venv.
# This ensures our script uses the installed dependencies.
ENTRYPOINT ["/opt/venv/bin/python", "ctfd_init.py"]
