FROM acidrain/python-poetry:3.11-alpine AS build

RUN apk add gcc libc-dev linux-headers uv;

WORKDIR /app
COPY pyproject.toml uv.lock /app/

RUN set -eu; \
    uv sync --all-extras --no-install-project


FROM python:3.11-alpine

USER nobody
WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

COPY --from=build /app/.venv /app/.venv
COPY acidrain_logging /app/acidrain_logging
