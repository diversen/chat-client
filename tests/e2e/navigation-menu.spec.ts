import { expect, test } from '@playwright/test';
import { login } from './helpers/auth';

test('main menu opens and shows logged-in links', async ({ page }) => {
  await login(page);

  const menu = page.locator('#main-menu-hamburger');
  await menu.click();

  await expect(menu).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.main-menu-overlay a[href="/user/profile"]')).toBeVisible();
  await expect(page.locator('.main-menu-overlay a[href="/prompt"]')).toBeVisible();
  await expect(page.locator('.main-menu-overlay a[href="/user/logout"]')).toBeVisible();
});
