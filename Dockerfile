FROM python:3.10-alpine AS build

RUN apk add curl gcc libc-dev linux-headers

RUN curl -LsSf https://astral.sh/uv/install.sh \
    | INSTALLER_NO_MODIFY_PATH=1 UV_INSTALL_DIR=/usr/local sh

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

RUN set -eu; \
    uv sync --all-extras


FROM python:3.10-alpine

USER nobody
WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

COPY --from=build /app/.venv /app/.venv
COPY acidrain_logging /app/acidrain_logging
