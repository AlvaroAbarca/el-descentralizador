# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.14
ARG DEBIAN_VERSION=bookworm
ARG BUILDER_IMAGE=python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION}

FROM ${BUILDER_IMAGE} AS python-base

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM python-base AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/app

COPY pyproject.toml README.md uv.lock ./
COPY src ./src
COPY medios_rss_actualizado.csv ./

RUN uv venv \
    && uv sync --no-dev --no-editable \
    && uv build

FROM python-base AS runtime

ARG LITESTAR_APP="el_descentralizador.server.asgi:create_app"

ENV PATH="/workspace/app/.venv/bin:/usr/local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LITESTAR_APP="${LITESTAR_APP}" \
    SAQ_USE_SERVER_LIFESPAN=false

RUN groupadd --system --gid 65532 nonroot \
    && useradd --no-create-home --system --uid 65532 --gid 65532 nonroot \
    && mkdir -p /workspace/app \
    && chown -R nonroot:nonroot /workspace

COPY --from=builder --chown=65532:65532 /workspace/app/.venv /workspace/app/.venv
COPY --from=builder --chown=65532:65532 /workspace/app/src /workspace/app/src
COPY --from=builder --chown=65532:65532 /workspace/app/medios_rss_actualizado.csv /workspace/app/medios_rss_actualizado.csv
COPY --from=builder --chown=65532:65532 /workspace/app/pyproject.toml /workspace/app/pyproject.toml
COPY alembic.ini /workspace/app/alembic.ini

WORKDIR /workspace/app
USER nonroot
STOPSIGNAL SIGINT
EXPOSE 8000

ENTRYPOINT ["tini", "--"]
CMD ["litestar", "run", "--host", "0.0.0.0", "--port", "8000"]
