import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { login } from './helpers/auth';

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

test('dialog deletion asks for confirmation before deleting', async ({ page }) => {
  ensureManagedTestUser();
  await login(page);

  const dialogId = await page.evaluate(async () => {
    const response = await fetch('/api/chat/dialogs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: `Playwright Dialog ${Date.now()}`,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create dialog: ${response.status}`);
    }

    const data = await response.json();
    return data.dialog_id;
  });

  expect(dialogId).toBeTruthy();
  await page.goto('/user/dialogs');

  const dialogRow = page.locator('.dialog').filter({ has: page.locator(`a[href="/chat/${dialogId}"]`) });
  await expect(dialogRow).toBeVisible();

  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toBe('Are you sure you want to delete this dialog?');
    await dialog.dismiss();
  });

  await dialogRow.locator('.delete').click();
  await expect(dialogRow).toBeVisible();

  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toBe('Are you sure you want to delete this dialog?');
    await dialog.accept();
  });

  await dialogRow.locator('.delete').click();
  await expect(dialogRow).toHaveCount(0);
});
