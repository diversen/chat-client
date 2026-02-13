import { expect, Page } from '@playwright/test';

const LOGIN_EMAIL = process.env.E2E_EMAIL || 'playwright@example.com';
const LOGIN_PASSWORD = process.env.E2E_PASSWORD || 'Playwright123!';

export async function login(page: Page): Promise<void> {
  await page.goto('/user/login');

  const alreadyLoggedIn = page.getByText('You are already logged in.');
  if (await alreadyLoggedIn.isVisible()) {
    await page.goto('/');
    await expect(page.locator('#message')).toBeVisible();
    return;
  }

  await page.fill('#email', LOGIN_EMAIL);
  await page.fill('#password', LOGIN_PASSWORD);
  await page.click('#login');

  await expect(page).toHaveURL(/\/($|chat\/)/);
  await expect(page.locator('#message')).toBeVisible();
}
