import { Page } from '@playwright/test';

export type BrowserErrorCollector = {
  reset: () => void;
  assertNoErrors: (pageLabel: string) => void;
};

type BrowserErrorRecord = {
  kind: 'pageerror' | 'console';
  message: string;
};

export function attachBrowserErrorCollector(page: Page): BrowserErrorCollector {
  const errors: BrowserErrorRecord[] = [];

  page.on('pageerror', (error) => {
    errors.push({
      kind: 'pageerror',
      message: error.stack || error.message,
    });
  });

  page.on('console', async (msg) => {
    if (msg.type() !== 'error') {
      return;
    }

    const location = msg.location();
    const locationText = location.url
      ? ` (${location.url}:${location.lineNumber}:${location.columnNumber})`
      : '';

    errors.push({
      kind: 'console',
      message: `${msg.text()}${locationText}`,
    });
  });

  return {
    reset() {
      errors.length = 0;
    },
    assertNoErrors(pageLabel: string) {
      if (errors.length === 0) {
        return;
      }

      const details = errors
        .map((error, index) => `${index + 1}. [${error.kind}] ${error.message}`)
        .join('\n');

      throw new Error(`Browser errors detected on ${pageLabel}\n${details}`);
    },
  };
}
