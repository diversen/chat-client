import { expect, test } from '@playwright/test';
import { login } from './helpers/auth';

test('main menu opens and shows logged-in links', async ({ page }) => {
  await login(page);

  const mainMenuButton = page.locator('#main-menu-hamburger');
  const topMenuOverlay = page.locator('.top-menu-overlay');

  await mainMenuButton.click();

  await expect(mainMenuButton).toHaveAttribute('aria-expanded', 'true');
  await expect(topMenuOverlay).toBeVisible();
  await expect(topMenuOverlay).toHaveAttribute('data-mode', 'main');
  await expect(topMenuOverlay.locator('.top-menu-panel-main a[href="/user/profile"]')).toBeVisible();
  await expect(topMenuOverlay.locator('.top-menu-panel-main a[href="/prompt"]')).toBeVisible();
  await expect(topMenuOverlay.locator('.top-menu-panel-main a[href="/user/logout"]')).toBeVisible();
});

test('custom prompt button switches to prompts mode and closes on outside click', async ({ page }) => {
  await login(page);

  const mainMenuButton = page.locator('#main-menu-hamburger');
  const customPromptButton = page.locator('#new-from-custom');
  const topMenuOverlay = page.locator('.top-menu-overlay');

  await customPromptButton.click();

  await expect(customPromptButton).toHaveAttribute('aria-expanded', 'true');
  await expect(mainMenuButton).toHaveAttribute('aria-expanded', 'false');
  await expect(topMenuOverlay).toBeVisible();
  await expect(topMenuOverlay).toHaveAttribute('data-mode', 'prompts');
  await expect(topMenuOverlay.locator('.top-menu-panel-prompts .overlay-header')).toContainText('Select a Custom Prompt');
  await expect(topMenuOverlay.locator('.top-menu-panel-prompts .prompt-item, .top-menu-panel-prompts .no-prompts-message').first()).toBeVisible();

  const emptyStateLink = topMenuOverlay.locator('.top-menu-panel-prompts .no-prompts-message');
  if (await emptyStateLink.count()) {
    await expect(emptyStateLink).toHaveAttribute('href', '/prompt/create');
    await expect(emptyStateLink).toHaveText('New Custom Prompt');
  }

  await page.locator('body').click({ position: { x: 5, y: 5 } });
  await expect(topMenuOverlay).toBeHidden();
  await expect(customPromptButton).toHaveAttribute('aria-expanded', 'false');
  await expect(mainMenuButton).toHaveAttribute('aria-expanded', 'false');
});
