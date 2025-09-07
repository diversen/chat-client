# E2E Testing with Playwright

This directory contains end-to-end (e2e) tests for the chat-client application using Playwright.

## Prerequisites

### 1. Install Dependencies

First, install the Node.js dependencies:
```bash
npm install
```

### 2. Install Playwright Browser

Install the Chromium browser for Playwright:
```bash
npx playwright install chromium
```

If the browser download fails, you may need to set up a proxy or download manually.

### 3. Setup Chat-Client Application

The tests require the chat-client server to be running. Follow these steps:

1. **Install Python dependencies:**
   ```bash
   pip install -e .
   ```

2. **Initialize the system:**
   ```bash
   chat-client init-system
   ```

3. **Create a test user:**
   ```bash
   chat-client create-user
   ```
   When prompted, use these credentials:
   - Email: `test@example.com`
   - Password: `test123`

4. **Configure for testing:**
   
   Edit `data/config.py` to ensure:
   - `SESSION_HTTPS_ONLY = False` (for local testing)
   - Comment out any ollama providers if not needed
   - Add at least one test model in `MODELS` dictionary

5. **Start the development server:**
   ```bash
   chat-client server-dev
   ```
   
   The server will run on `http://localhost:8000`

## Running Tests

With the server running in one terminal, run the tests in another:

```bash
npx playwright test
```

## Test Coverage

The e2e tests cover:

### Unauthenticated Pages
- Login page (`/user/login`)
- Signup page (`/user/signup`) 
- Password reset page (`/user/reset`)
- Captcha endpoint (`/captcha`)
- Redirect behavior for protected pages

### Authentication Flow  
- User login functionality
- User logout functionality
- Session management

### Authenticated Pages
- Main chat page (`/`)
- User profile (`/user/profile`)
- User dialogs (`/user/dialogs`)  
- Prompts list (`/prompt`)
- Create prompt page (`/prompt/create`)
- Logout page (`/user/logout`)

### API Endpoints
- Models list (`/list`)
- Configuration (`/config`)
- Authentication requirements

### Error Handling
- 404 page handling
- Error logging endpoint (`/error/log`)

### Static Files
- CSS files serving
- JavaScript files serving

## Test Structure

- `example.spec.js` - Original simple test
- `pages.spec.js` - Comprehensive page and API tests

## Troubleshooting

### Browser Installation Issues
If `npx playwright install chromium` fails:
1. Try running with a proxy if you're behind corporate firewall
2. Check network connectivity 
3. Try installing all browsers: `npx playwright install`

### Server Connection Issues
- Ensure chat-client server is running on port 8000
- Check that the test user exists with correct credentials
- Verify `data/config.py` is configured correctly

### Test Failures
- Check server logs in `data/main.log`
- Verify database was initialized properly
- Ensure no other service is using port 8000