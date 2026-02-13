import { expect, test } from '@playwright/test';
import { login } from './helpers/auth';

test('login redirects to chat page', async ({ page }) => {
  await login(page);

  await expect(page.locator('body')).toHaveClass(/page-chat/);
  await expect(page.locator('#responses')).toBeVisible();
  await expect(page.locator('#send')).toBeVisible();
});
