import { test, expect } from '@playwright/test';

test.describe('Ingestion dashboard', () => {
  test('home page links to dashboard', async ({ page }) => {
    await page.goto('/');
    // New design uses "Ingest" link in navigation or CTA buttons
    await expect(page.getByRole('link', { name: /ingest/i }).first()).toBeVisible();
  });
});
