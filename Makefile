.PHONY: test test-unit test-int lint typecheck clean eval demo

PYTHON := python
PYTEST := pytest
RUFF := ruff
MYPY := mypy

lint:
	$(RUFF) check .

typecheck:
	$(MYPY) changeproof

test-unit:
	$(PYTEST) tests/unit -v

test-int:
	$(PYTEST) tests/integration -v

test: test-unit test-int

eval:
	$(PYTHON) evaluation/evaluate.py

clean:
	@rm -rf runs/* capsules/* __pycache__ .pytest_cache .mypy_cache .ruff_cache tests/__pycache__ changeproof/__pycache__
