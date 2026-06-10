#!/bin/sh
set -e

CHECK_PATHS="chat_client tests bin"

echo "Running ruff format ..."
ruff format $CHECK_PATHS --check

echo "Running mypy ..."
mypy  --config-file pyproject.toml chat_client 

echo "Running ruff check ..."
ruff check $CHECK_PATHS

echo "Running tests ..."
./run-all-tests.sh
