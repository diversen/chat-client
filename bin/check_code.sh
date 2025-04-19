#!/bin/sh
echo "Running black ..."
black . --config pyproject.toml

echo "Running mypy ..."
mypy  --config-file pyproject.toml chat_client

echo "Running flake8 ..."
flake8 . --config .flake8
