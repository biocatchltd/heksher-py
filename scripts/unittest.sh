# run the unittests with branch coverage
poetry run python -m pytest --cov=./heksher --cov-report=xml --cov-report=term-missing tests/