# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY legacy_lens ./legacy_lens

RUN pip install --no-cache-dir ".[mysql]"

WORKDIR /work

ENTRYPOINT ["legacy-lens"]
CMD ["--help"]
