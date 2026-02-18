#!/bin/sh
echo "Running black ..."
black . --config pyproject.toml --extend-exclude '/chat_client/migrations/'

echo "Running mypy ..."
mypy  --config-file pyproject.toml chat_client 

echo "Running flake8 ..."
flake8 . -j 1 --config .flake8
