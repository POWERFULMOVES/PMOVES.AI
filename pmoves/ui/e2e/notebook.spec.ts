import { test, expect } from '@playwright/test';

test.describe('Notebook dashboard', () => {
  test('renders heading and navigation', async ({ page }) => {
    await page.goto('/dashboard/notebook');

    await expect(
      page.getByRole('heading', { name: /open notebook/i })
    ).toBeVisible();

    // DashboardNavigation should be present with notebook active
    await expect(page.getByRole('navigation')).toBeVisible();

    // No redirect to login (single-user mode)
    await expect(page.getByRole('link', { name: /login/i })).toHaveCount(0);
  });

  test('notebook runtime page renders status section', async ({ page }) => {
    await page.goto('/dashboard/notebook/runtime');

    await expect(
      page.getByRole('heading', { name: /notebook runtime/i })
    ).toBeVisible();

    // Service Status card should be present
    await expect(
      page.getByRole('heading', { name: /service status/i })
    ).toBeVisible();

    // Health indicator dot should exist (healthy, error, or unknown)
    await expect(page.getByTestId('health-indicator')).toBeVisible();
  });

  test('notebook sources API returns valid shape', async ({ request }) => {
    const res = await request.get('/api/notebook/sources');

    // Accept either success or graceful degradation (503 = not configured, 502 = upstream down)
    expect([200, 502, 503]).toContain(res.status());

    const json = await res.json();
    expect(json).toHaveProperty('items');
    expect(Array.isArray(json.items)).toBe(true);

    if (res.status() === 200) {
      expect(json).toHaveProperty('endpoint');
    }
    if (res.status() === 503) {
      expect(json.error).toContain('not configured');
    }
  });

  test('notebook runtime API returns valid shape', async ({ request }) => {
    const res = await request.get('/api/notebook/runtime');

    // Accept success or graceful degradation
    expect([200, 503]).toContain(res.status());

    const json = await res.json();
    expect(json).toHaveProperty('service', 'notebook-sync');
    expect(json).toHaveProperty('endpoint');
    expect(json).toHaveProperty('health');
  });

  test('health/all alias resolves same as health-all', async ({ request }) => {
    const [aliasRes, canonicalRes] = await Promise.all([
      request.get('/api/health/all'),
      request.get('/api/health-all'),
    ]);

    // Both should succeed
    expect(aliasRes.status()).toBe(200);
    expect(canonicalRes.status()).toBe(200);

    const aliasJson = await aliasRes.json();
    const canonicalJson = await canonicalRes.json();

    // Both should have the same shape (services array + percentage)
    expect(aliasJson).toHaveProperty('services');
    expect(canonicalJson).toHaveProperty('services');
    expect(aliasJson).toHaveProperty('percentage');
    expect(canonicalJson).toHaveProperty('percentage');

    // Service count and percentage should match between alias and canonical
    expect(aliasJson.services.length).toBe(canonicalJson.services.length);
    expect(aliasJson.percentage).toBe(canonicalJson.percentage);
  });

  test('Open Notebook card visible on services dashboard', async ({ page }) => {
    await page.goto('/dashboard/services');

    await expect(
      page.getByRole('heading', { name: /services/i })
    ).toBeVisible();

    // Open Notebook (Cataclysm) should appear as a service card
    await expect(
      page.getByRole('link', { name: /open notebook/i }).first()
    ).toBeVisible();
  });
});
