# run the unittests with branch coverage
poetry run python -m pytest --cov=./<$package$> --cov-report=xml --cov-report=term-missing tests/