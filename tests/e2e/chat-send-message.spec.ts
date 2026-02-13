import { expect, test } from '@playwright/test';
import { login } from './helpers/auth';

test('send a message and render assistant response', async ({ page }) => {
  await page.route('**/chat', async (route) => {
    const sseBody = [
      'data: {"choices":[{"delta":{"content":"Playwright test response"}}]}',
      'data: [DONE]',
      '',
    ].join('\n');

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: sseBody,
    });
  });

  await login(page);

  await page.fill('#message', 'Hello from Playwright');
  await page.click('#send');

  await expect(page.locator('.user-message .content').last()).toContainText('Hello from Playwright');
  await expect(page.locator('.assistant-message .content').last()).toContainText('Playwright test response');
});
