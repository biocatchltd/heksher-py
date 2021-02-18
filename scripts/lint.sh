#!/bin/sh
# run various linters
set -e
poetry run flake8 --max-line-length 120 heksher
set +e
poetry run python -c "import pytype"
res=$?
set -e
if [ "$res" -ne "0" ]
  then
    echo "pytype not run, please run in python 3.8 or lower"
  else
    poetry run pytype --keep-going heksher
fi
