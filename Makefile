.PHONY: all

lint: .PHONY
	pre-commit run --all-files

test: .PHONY
	poetry run pytest \
		--cov --cov-fail-under 100 \
		--cov-report=term-missing:skip-covered \
		--verbosity=1

install: .PHONY
	poetry install --sync --all-extras

update: poetry.lock install

poetry.lock: .PHONY
	poetry update --lock
