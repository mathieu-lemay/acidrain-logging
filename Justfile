lint:
    pre-commit run --all-files

test:
    uv run pytest \
        --cov --cov-fail-under 100 \
        --cov-report=term-missing:skip-covered \
        --verbosity=1

install:
    uv sync --all-extras

update: _uv_lock install

_uv_lock:
    uv lock --upgrade
