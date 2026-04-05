import { expect, test, Page } from '@playwright/test';
import { login } from './helpers/auth';
import { attachBrowserErrorCollector, BrowserErrorCollector } from './helpers/browser-errors';

type SmokePage = {
  path: string;
  ready: (page: Page) => Promise<void>;
};

const publicPages: SmokePage[] = [
  {
    path: '/user/login',
    ready: async (page) => {
      await expect(page.locator('#login')).toBeVisible();
    },
  },
  {
    path: '/user/signup',
    ready: async (page) => {
      await expect(page.locator('#signup-form')).toBeVisible();
    },
  },
  {
    path: '/user/password/reset',
    ready: async (page) => {
      await expect(page.locator('#reset-form')).toBeVisible();
    },
  },
];

const authenticatedPages: SmokePage[] = [
  {
    path: '/',
    ready: async (page) => {
      await expect(page.locator('body')).toHaveClass(/page-chat/);
      await expect(page.locator('#message')).toBeVisible();
    },
  },
  {
    path: '/user/profile',
    ready: async (page) => {
      await expect(page.locator('body')).toHaveClass(/page-profile/);
      await expect(page.locator('#save')).toBeVisible();
    },
  },
  {
    path: '/user/dialogs',
    ready: async (page) => {
      await expect(page.locator('body')).toHaveClass(/page-dialogs/);
      await expect(page.locator('#dialogs-search-input')).toBeVisible();
      await expect
        .poll(async () => {
          return await page.locator('#loading').evaluate((element) => {
            return element.classList.contains('hidden');
          });
        })
        .toBe(true);
    },
  },
  {
    path: '/prompts',
    ready: async (page) => {
      await expect(page.getByRole('heading', { name: 'Your Prompts' })).toBeVisible();
    },
  },
  {
    path: '/prompts/new',
    ready: async (page) => {
      await expect(page.locator('#create-form')).toBeVisible();
    },
  },
];

async function visitAndAssertNoErrors(page: Page, smokePage: SmokePage, browserErrors: BrowserErrorCollector): Promise<void> {
  browserErrors.reset();

  await page.goto(smokePage.path, { waitUntil: 'domcontentloaded' });
  await smokePage.ready(page);
  await page.waitForTimeout(250);

  browserErrors.assertNoErrors(smokePage.path);
}

test.describe('console smoke coverage', () => {
  test('public pages render without browser errors', async ({ page }) => {
    const browserErrors = attachBrowserErrorCollector(page);

    for (const smokePage of publicPages) {
      await visitAndAssertNoErrors(page, smokePage, browserErrors);
    }
  });

  test('authenticated pages render without browser errors', async ({ page }) => {
    const browserErrors = attachBrowserErrorCollector(page);

    await login(page);

    for (const smokePage of authenticatedPages) {
      await visitAndAssertNoErrors(page, smokePage, browserErrors);
    }
  });
});
