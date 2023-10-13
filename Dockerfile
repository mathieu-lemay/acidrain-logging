FROM acidrain/python-poetry:3.7-alpine AS build

RUN apk add gcc libc-dev linux-headers

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

RUN set -eu; \
    poetry config virtualenvs.in-project true; \
    poetry install --all-extras --no-root


FROM python:3.7-alpine

USER nobody
WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

COPY --from=build /app/.venv /app/.venv
COPY acidrain_logging /app/acidrain_logging
