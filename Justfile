lint:
    pre-commit run --all-files

test:
    poetry run pytest \
        --cov --cov-fail-under 100 \
        --cov-report=term-missing:skip-covered \
        --verbosity=1

install:
    poetry sync --all-extras

update: _poetry_lock install

_poetry_lock:
    poetry update --lock
