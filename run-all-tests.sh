#!/usr/bin/env bash

set -euo pipefail

echo "==> Backend tests"
python tests/run_all_tests.py

echo
echo "==> JavaScript helper tests"
npm run test:js

echo
echo "==> Playwright E2E tests"
npm run e2e
