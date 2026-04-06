import { expect, test } from '@playwright/test';
import { login } from './helpers/auth';

test('loading spinner stays hidden when opening chat from prompt id', async ({ page }) => {
  await login(page);

  const promptId = await page.evaluate(async () => {
    const response = await fetch('/api/prompts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: `Playwright Prompt ${Date.now()}`,
        prompt: 'Prompt content for spinner behavior test',
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create prompt: ${response.status}`);
    }

    const data = await response.json();
    return data.prompt_id;
  });

  expect(promptId).toBeTruthy();
  await page.goto(`/?id=${promptId}`);

  const spinner = page.locator('.loading-spinner');
  await expect(spinner).toBeHidden();
  await expect(page.locator('#responses .user-message').first()).toBeVisible();
});
