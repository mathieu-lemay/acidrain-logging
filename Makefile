.PHONY: all
.NOTPARALLEL:

lint: .PHONY
	pre-commit run --all-files

test: .PHONY
	uv run pytest \
		--cov --cov-fail-under 100 \
		--cov-report=term-missing:skip-covered \
		--verbosity=1

install: .PHONY
	uv sync --all-extras

update: uv.upgrade install

uv.upgrade: .PHONY
	uv lock --upgrade
