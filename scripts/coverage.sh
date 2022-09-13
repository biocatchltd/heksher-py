#!/bin/sh
set -e

coverage run --branch --context=ut --include="heksher/*" -m pytest tests/unittest "$@"
coverage run -a --branch --context=blackbox --include="heksher/*" -m pytest tests/blackbox/app "$@"

coverage html
coverage report -m
coverage xml