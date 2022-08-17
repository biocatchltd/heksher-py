#!/bin/sh
# run the unittests with branch coverage
python -m pytest --cov=./heksher --cov-report=xml --cov-report=term-missing tests/unittest "$@"
python -m pytest --cov=./heksher --cov-report=xml --cov-report=term-missing tests/blackbox/app "$@"

