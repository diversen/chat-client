# Tests

Run tests from the project root.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
chat-client init-system
```

## Backend

No server needs to be started.

```bash
python tests/test_starlette_simple.py
python tests/test_starlette_comprehensive.py
python tests/run_all_tests.py
```

## E2E

Install Node and Playwright dependencies first:

```bash
npm install
npx playwright install
```

Managed mode starts its own server and bootstraps its own test user:

```bash
npm run e2e
```

For more E2E details, see `tests/e2e/README.md`.
