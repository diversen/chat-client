import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:8010';
const baseUrlObj = new URL(baseURL);
const serverHost = baseUrlObj.hostname || '127.0.0.1';
const serverPort = Number(baseUrlObj.port || (baseUrlObj.protocol === 'https:' ? 443 : 80));
const useManagedWebServer = process.env.E2E_MANAGED_SERVER === '1';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: useManagedWebServer
    ? {
        command:
          'SKIP_PROVIDER_MODEL_DISCOVERY=1 SESSION_HTTPS_ONLY=0 python -m chat_client.cli init-system && ' +
          'SKIP_PROVIDER_MODEL_DISCOVERY=1 SESSION_HTTPS_ONLY=0 python -m chat_client.cli create-user --email "playwright@example.com" --password "Playwright123!" && ' +
          `SKIP_PROVIDER_MODEL_DISCOVERY=1 SESSION_HTTPS_ONLY=0 python -m uvicorn chat_client.main:app --host ${serverHost} --port ${serverPort}`,
        url: baseURL,
        timeout: 120 * 1000,
        reuseExistingServer: !process.env.CI,
      }
    : undefined,
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
