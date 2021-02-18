#!/bin/sh
# install the dev-dependencies of the project
pip install poetry

poetry update --lock
poetry install