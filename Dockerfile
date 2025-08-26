# syntax=docker/dockerfile:1.4

FROM python:3.12-alpine AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ctfd_init.py ./ctfd_init.py
RUN adduser -D -H -u 65532 appuser
USER 65532
ENTRYPOINT ["python", "/app/ctfd_init.py"]
