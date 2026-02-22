import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { login } from './helpers/auth';

function ensureManagedTestUser(): void {
  if (process.env.E2E_MANAGED_SERVER !== '1') return;
  execSync(
    'SKIP_PROVIDER_MODEL_DISCOVERY=1 SESSION_HTTPS_ONLY=0 python -m chat_client.cli create-user --email "playwright@example.com" --password "Playwright123!"',
    { stdio: 'inherit' },
  );
}

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

test('second user message aligns directly below top bar after short assistant reply', async ({ page }) => {
  ensureManagedTestUser();

  let chatRequestCount = 0;

  await page.route('**/chat', async (route) => {
    chatRequestCount += 1;
    const assistantText = chatRequestCount === 1 ? 'ok' : 'second response';
    const sseBody = [
      `data: {"choices":[{"delta":{"content":"${assistantText}"}}]}`,
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

  await page.fill('#message', 'First message');
  await page.click('#send');
  await expect(page.locator('.assistant-message .content').last()).toContainText('ok');

  await page.fill('#message', 'Second message');
  await page.click('#send');

  const secondUserMessage = page.locator('.user-message').nth(1);
  await expect(secondUserMessage.locator('.content')).toContainText('Second message');

  await expect
    .poll(async () => {
      return await page.evaluate(() => {
        const topBar = document.querySelector('.top-bar');
        const secondUser = document.querySelectorAll('.user-message')[1];
        if (!topBar || !secondUser) return null;
        const navBottom = topBar.getBoundingClientRect().bottom;
        const messageTop = secondUser.getBoundingClientRect().top;
        return Math.abs(messageTop - navBottom);
      });
    })
    .toBeLessThanOrEqual(3);
});
