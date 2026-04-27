# Tests

Run tests from the project root.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
npm install
npx playwright install
chat-client init-system
```

## All Test Types

Run everything from the project root:

```bash
./run-all-tests.sh
```

## Backend

No server needs to be started.

```bash
python tests/test_starlette_simple.py
python tests/test_starlette_comprehensive.py
python tests/run_all_tests.py
```

## JavaScript Helpers

Pure JavaScript helper tests run with Node's built-in test runner:

```bash
npm run test:js
```

## E2E

Managed mode starts its own server and bootstraps its own test user:

```bash
npm run e2e
```

For more E2E details, see `tests/e2e/README.md`.
