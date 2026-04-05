import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { login } from './helpers/auth';

const MESSAGE_TOP_BAR_GAP_PX = 16;

function ensureManagedTestUser(): void {
  if (process.env.E2E_MANAGED_SERVER !== '1') return;
  execSync(
    'SKIP_PROVIDER_MODEL_DISCOVERY=1 SESSION_HTTPS_ONLY=0 python -m chat_client.cli init-system',
    { stdio: 'inherit' },
  );
  execSync(
    "SKIP_PROVIDER_MODEL_DISCOVERY=1 SESSION_HTTPS_ONLY=0 python - <<'PY'\n" +
      'import asyncio\n' +
      'from chat_client.cli import _create_user\n' +
      "asyncio.run(_create_user('playwright@example.com', 'Playwright123!'))\n" +
      'PY',
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
      return await page.evaluate((messageTopBarGapPx) => {
        const topBar = document.querySelector('.top-bar');
        const secondUser = document.querySelectorAll('.user-message')[1];
        if (!topBar || !secondUser) return null;
        const navBottom = topBar.getBoundingClientRect().bottom;
        const messageTop = secondUser.getBoundingClientRect().top;
        return Math.abs(messageTop - (navBottom + messageTopBarGapPx));
      }, MESSAGE_TOP_BAR_GAP_PX);
    })
    .toBeLessThanOrEqual(3);
});

test('renders valid KaTeX, preserves prose dollars, and highlights invalid expressions', async ({ page }) => {
  ensureManagedTestUser();

  await page.route('**/chat', async (route) => {
    const assistantText = [
      'Valid display math:',
      '',
      String.raw`\[`,
      String.raw`\prod_{j=1}^{i-1}(i^i)_j = \prod_{j=1}^{i-1}\bigl(i^i\bmod j\bigr).`,
      String.raw`\]`,
      '',
      'Inline math still works: $(i^i)_m$.',
      '',
      'Currency-style prose should stay prose: price is $5 today.',
      '',
      'Broken math should be highlighted: $\\prod_{i=2}^{12} (i^i)_\\prod$.',
    ].join('\n');

    const sseBody = [
      `data: ${JSON.stringify({ choices: [{ delta: { content: assistantText } }] })}`,
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

  await page.fill('#message', 'Test KaTeX rendering');
  await page.click('#send');

  const assistantContent = page.locator('.assistant-message .content').last();
  await expect(assistantContent).toContainText('Valid display math:');
  await expect(assistantContent.locator('.katex-display')).toHaveCount(1);
  await expect(assistantContent.locator('.katex')).toHaveCount(2);
  await expect(assistantContent).toContainText('price is $5 today.');

  const katexError = assistantContent.locator('.katex-error');
  await expect(katexError).toHaveCount(1);
  await expect(katexError).toContainText(String.raw`$\prod_{i=2}^{12} (i^i)_\prod$`);
});
