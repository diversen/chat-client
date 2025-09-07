// @ts-check
import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('http://localhost:8000/user/login');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Login/);
});

