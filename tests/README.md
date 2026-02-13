# Tests

Run tests from the project root.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
chat-client init-system
```

## Backend tests

No server needs to be started.
No user needs to be created manually.
Ollama must be running and reachable at the configured endpoint (default `http://localhost:11434/v1`), otherwise app import can exit before tests run.

```bash
python tests/test_starlette_simple.py
python tests/test_starlette_comprehensive.py
python tests/run_all_tests.py
```

## E2E tests

For `npm run e2e`, start the app yourself and make sure the e2e user exists.

```bash
# Start app for local e2e mode
chat-client server-dev

# In another terminal, create the user used by E2E_EMAIL/E2E_PASSWORD if needed
chat-client create-user

# Use an already running server at http://localhost:8000
E2E_EMAIL=test E2E_PASSWORD=test npm run e2e

# Or let Playwright start its own server
npm run e2e:managed
```
