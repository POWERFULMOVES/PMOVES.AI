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

  // These API routes require an authenticated owner since #969 (2026-03-16, authenticateRequest /
  // ownerFromJwt). With no session they must refuse with 401 + a JSON error, never leak data.
  // The authenticated path needs a live Supabase-issued JWT: see the @backend note in services-health.spec.ts.
  test('notebook sources API returns valid shape', async ({ request }) => {
    const res = await request.get('/api/notebook/sources');

    expect(res.status()).toBe(401);
    const json = await res.json();
    expect(json).toHaveProperty('items');
    expect(Array.isArray(json.items)).toBe(true);
    expect(json.items).toHaveLength(0);
    expect(typeof json.error).toBe('string');
  });

  test('notebook runtime API returns valid shape', async ({ request }) => {
    const res = await request.get('/api/notebook/runtime');

    expect(res.status()).toBe(401);
    const json = await res.json();
    expect(typeof json.error).toBe('string');
  });

  test('health/all alias resolves same as health-all', async ({ request }) => {
    const [aliasRes, canonicalRes] = await Promise.all([
      request.get('/api/health/all'),
      request.get('/api/health-all'),
    ]);

    // The alias delegates to the canonical handler, so both must answer identically.
    // Unauthenticated, that is the auth gate: 401 with the same JSON body.
    expect(aliasRes.status()).toBe(canonicalRes.status());
    expect(aliasRes.status()).toBe(401);
    expect(await aliasRes.json()).toEqual(await canonicalRes.json());
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
