# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.12.13-slim-trixie
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.32

FROM --platform=${BUILDPLATFORM} ${UV_IMAGE} AS build-uv

FROM --platform=${BUILDPLATFORM} ${PYTHON_IMAGE} AS package-builder

COPY --from=build-uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv build --wheel --out-dir /dist

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS builder

COPY --from=uv /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

COPY --from=package-builder /dist /dist

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/.venv/bin/python --no-deps /dist/trussium-*.whl

FROM ${PYTHON_IMAGE} AS runtime

ARG BUILD_DATE="unknown"
ARG VERSION="dev"
ARG VCS_REF="unknown"
ARG SOURCE_URL="https://github.com/trussiumhq/trussium"

LABEL org.opencontainers.image.title="Trussium" \
      org.opencontainers.image.description="Cloud-native runtime for AI applications." \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Apache-2.0"

RUN groupadd --gid 10001 trussium \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin trussium

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRUSSIUM_RUNTIME__HOST=0.0.0.0 \
    TRUSSIUM_RUNTIME__PORT=9000

WORKDIR /app

COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 LICENSE /app/LICENSE

USER 10001:10001

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/health/live', timeout=2).read()"]

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "-m", "trussium"]
