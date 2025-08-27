# syntax=docker/dockerfile:1.4

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
USER 65532
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/bin/python3", "/app/ctfd_init.py"]
