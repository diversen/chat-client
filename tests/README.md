# Tests

Run tests from the project root.

## Backend tests

```bash
python tests/test_starlette_simple.py
python tests/test_starlette_comprehensive.py
python tests/run_all_tests.py
```

## E2E tests

```bash
# Use an already running server at http://localhost:8000
E2E_EMAIL=test E2E_PASSWORD=test npm run e2e

# Or let Playwright start its own server
npm run e2e:managed
```
