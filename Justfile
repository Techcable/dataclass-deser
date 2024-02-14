mypy:
    mypy src

format-check:
    black --check .
    isort --check .

format:
    black .
    isort .
 
lint: mypy format-check

test: && lint
    tox run -qm test
