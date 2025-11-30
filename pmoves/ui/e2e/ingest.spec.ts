import { test, expect } from '@playwright/test';

test.describe('Ingestion dashboard', () => {
  test('home page links to dashboard', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /ingestion dashboard/i })).toBeVisible();
  });
});
