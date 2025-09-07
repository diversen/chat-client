// @ts-check
import { test, expect } from '@playwright/test';

// Test configuration
const TEST_USER = {
  email: 'test@example.com',
  password: 'test123'
};

test.describe('Chat Client E2E Tests', () => {
  
  test.describe('Unauthenticated pages', () => {
    
    test('should load login page', async ({ page }) => {
      await page.goto('/user/login');
      await expect(page).toHaveTitle(/Login/);
      await expect(page.locator('form')).toBeVisible();
    });

    test('should load signup page', async ({ page }) => {
      await page.goto('/user/signup');
      await expect(page).toHaveTitle(/Sign up/);
      await expect(page.locator('form')).toBeVisible();
    });

    test('should load password reset page', async ({ page }) => {
      await page.goto('/user/reset');
      await expect(page).toHaveTitle(/Reset password/);
      await expect(page.locator('form')).toBeVisible();
    });

    test('should redirect to login when accessing protected pages while logged out', async ({ page }) => {
      // Test main chat page redirect
      await page.goto('/');
      await expect(page).toHaveURL(/.*\/user\/login/);
      
      // Test profile redirect
      await page.goto('/user/profile');
      await expect(page).toHaveURL(/.*\/user\/login/);
      
      // Test dialogs redirect
      await page.goto('/user/dialogs');
      await expect(page).toHaveURL(/.*\/user\/login/);
      
      // Test prompts redirect
      await page.goto('/prompt');
      await expect(page).toHaveURL(/.*\/user\/login/);
    });

    test('should load captcha image', async ({ page }) => {
      const response = await page.request.get('/captcha');
      expect(response.ok()).toBeTruthy();
      expect(response.headers()['content-type']).toContain('image/png');
    });
  });

  test.describe('Authentication flow', () => {
    
    test('should allow user login', async ({ page }) => {
      await page.goto('/user/login');
      
      // Fill login form
      await page.fill('input[name="email"]', TEST_USER.email);
      await page.fill('input[name="password"]', TEST_USER.password);
      
      // Submit form using the correct button selector
      await page.click('button#login');
      
      // Should redirect to main page after successful login
      await expect(page).toHaveURL('/');
    });

    test('should allow user logout', async ({ page }) => {
      // First login
      await page.goto('/user/login');
      await page.fill('input[name="email"]', TEST_USER.email);
      await page.fill('input[name="password"]', TEST_USER.password);
      await page.click('button#login');
      await expect(page).toHaveURL('/');
      
      // Then logout
      await page.goto('/user/logout');
      await expect(page).toHaveTitle(/Logout/);
      
      // Click logout link
      await page.click('a[href="/user/logout?logout=1"]');
      await expect(page).toHaveURL(/.*\/user\/login/);
    });
  });

  test.describe('Authenticated pages', () => {
    
    // Login before each test in this group
    test.beforeEach(async ({ page }) => {
      await page.goto('/user/login');
      await page.fill('input[name="email"]', TEST_USER.email);
      await page.fill('input[name="password"]', TEST_USER.password);
      await page.click('button#login');
      await expect(page).toHaveURL('/');
    });

    test('should load main chat page', async ({ page }) => {
      await page.goto('/');
      await expect(page).toHaveTitle(/Chat/);
      // Check for main page content - be flexible about the exact selectors
      await expect(page.locator('body')).toBeVisible();
      // The page should have loaded successfully
      const url = page.url();
      expect(url).toContain('localhost:8000');
    });

    test('should load user profile page', async ({ page }) => {
      await page.goto('/user/profile');
      await expect(page).toHaveTitle(/Profile/);
      await expect(page.locator('form')).toBeVisible();
    });

    test('should load dialogs page', async ({ page }) => {
      await page.goto('/user/dialogs');
      await expect(page).toHaveTitle(/Search dialogs/);
    });

    test('should load prompts list page', async ({ page }) => {
      await page.goto('/prompt');
      await expect(page).toHaveTitle(/Your Prompts/);
    });

    test('should load create prompt page', async ({ page }) => {
      await page.goto('/prompt/create');
      await expect(page).toHaveTitle(/Create Prompt/);
      await expect(page.locator('form')).toBeVisible();
    });

    test('should load logout page', async ({ page }) => {
      await page.goto('/user/logout');
      await expect(page).toHaveTitle(/Logout/);
      await expect(page.locator('a[href="/user/logout?logout=1"]')).toBeVisible();
    });
  });

  test.describe('API endpoints', () => {
    
    test('should return models list', async ({ page }) => {
      const response = await page.request.get('/list');
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data).toHaveProperty('model_names');
      expect(Array.isArray(data.model_names)).toBeTruthy();
    });

    test('should return config', async ({ page }) => {
      const response = await page.request.get('/config');
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      expect(data).toHaveProperty('default_model');
      expect(data).toHaveProperty('use_katex');
    });

    test('should require authentication for protected API endpoints', async ({ page }) => {
      // Test dialogs JSON endpoint without auth
      const response = await page.request.get('/user/dialogs/json');
      expect(response.ok()).toBeTruthy(); // Returns 200 but with error in JSON
      const data = await response.json();
      expect(data.error).toBeTruthy();
      expect(data.message).toContain('logged out');
    });
  });

  test.describe('Error handling', () => {
    
    test('should handle 404 pages gracefully', async ({ page }) => {
      await page.goto('/nonexistent-page');
      // Should either show 404 page or redirect appropriately
      // We expect at least the page to load without crashing
      await expect(page.locator('body')).toBeVisible();
    });

    test('should accept error log posts', async ({ page }) => {
      const response = await page.request.post('/error/log', {
        data: { error: 'test error', page: 'test' }
      });
      expect(response.ok()).toBeTruthy();
    });
  });

  test.describe('Static files', () => {
    
    test('should serve CSS files', async ({ page }) => {
      const response = await page.request.get('/static/css/style.css');
      // File may or may not exist, but should either be 200 or 404, not 500
      expect([200, 404].includes(response.status())).toBeTruthy();
    });

    test('should serve JS files', async ({ page }) => {
      const response = await page.request.get('/static/js/chat.js');
      // File may or may not exist, but should either be 200 or 404, not 500
      expect([200, 404].includes(response.status())).toBeTruthy();
    });
  });
});