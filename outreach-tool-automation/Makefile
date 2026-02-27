.PHONY: format lint typecheck test check

format:
	black src tests
	ruff check src tests --fix

lint:
	ruff check src tests

typecheck:
	mypy src tests

test:
	pytest

check: lint typecheck test
