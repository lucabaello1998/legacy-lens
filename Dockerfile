# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY legacy_lens ./legacy_lens

RUN pip install --no-cache-dir ".[mysql]"

# Usuario sin privilegios: el contenedor solo lee el código analizado y escribe
# en /work. Como root, los informes quedaban con dueño root en el host.
RUN useradd --create-home --uid 1000 escaner \
    && mkdir -p /work /out \
    && chown -R escaner:escaner /work /out

USER escaner
WORKDIR /work

ENTRYPOINT ["legacy-lens"]
CMD ["--help"]
