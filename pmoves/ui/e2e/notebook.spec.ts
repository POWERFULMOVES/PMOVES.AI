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
  // ownerFromJwt). The default run has no session, so the next three tests cover ONLY the auth
  // gate: unauthenticated requests must be refused with 401 + a JSON error and never leak data.
  // The success shapes are asserted separately by the ORIGINAL tests (same names as on main),
  // restored in the @backend describe block at the end of this file.
  test('notebook sources API refuses unauthenticated requests', async ({ request }) => {
    const res = await request.get('/api/notebook/sources');

    expect(res.status()).toBe(401);
    const json = await res.json();
    expect(json).toHaveProperty('items');
    expect(Array.isArray(json.items)).toBe(true);
    expect(json.items).toHaveLength(0);
    expect(typeof json.error).toBe('string');
  });

  test('notebook runtime API refuses unauthenticated requests', async ({ request }) => {
    const res = await request.get('/api/notebook/runtime');

    expect(res.status()).toBe(401);
    const json = await res.json();
    expect(typeof json.error).toBe('string');
  });

  test('health/all alias refuses unauthenticated requests like health-all', async ({ request }) => {
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

/**
 * @backend: success shapes of the owner-gated routes, restored from origin/main with their
 * original names and assertions. On main they ran unauthenticated, so after #969 they could only
 * ever see 401; here they send a session.
 *
 * Needs a live stack AND a session. Auth comes from the E2E_AUTH_TOKEN environment variable: a
 * Supabase-issued access token (a JWT with a `sub` claim), sent as `Authorization: Bearer`, which
 * is what authenticateRequest() reads first. Without it every test here SKIPS with that message;
 * none passes vacuously and none fails for want of credentials.
 *
 *   E2E_AUTH_TOKEN=<access token> npm run test:e2e:backend
 */
const E2E_AUTH_TOKEN = process.env.E2E_AUTH_TOKEN;
const NO_TOKEN_MSG =
  'E2E_AUTH_TOKEN is not set: owner-gated routes need a Supabase access token (Bearer JWT with a sub claim)';
const authHeaders = () => ({ Authorization: `Bearer ${E2E_AUTH_TOKEN}` });

test.describe('Notebook API (authenticated)', { tag: '@backend' }, () => {
  test.skip(!E2E_AUTH_TOKEN, NO_TOKEN_MSG);

  test('notebook sources API returns valid shape', async ({ request }) => {
    // This route still uses the deprecated ownerFromJwt(), which IGNORES the Authorization header
    // and authenticates with the UI server's boot JWT only. The header is sent for when it moves to
    // authenticateRequest(); until then a 401 here means the server under test has no boot JWT
    // configured (single-user operator mode), not that E2E_AUTH_TOKEN is bad.
    const res = await request.get('/api/notebook/sources', { headers: authHeaders() });

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
    const res = await request.get('/api/notebook/runtime', { headers: authHeaders() });

    // Accept success or graceful degradation
    expect([200, 503]).toContain(res.status());

    const json = await res.json();
    expect(json).toHaveProperty('service', 'notebook-sync');
    expect(json).toHaveProperty('endpoint');
    expect(json).toHaveProperty('health');
  });

  test('health/all alias resolves same as health-all', async ({ request }) => {
    const [aliasRes, canonicalRes] = await Promise.all([
      request.get('/api/health/all', { headers: authHeaders() }),
      request.get('/api/health-all', { headers: authHeaders() }),
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

    // Service count and percentage should match between alias and canonical (authenticated bodies).
    // These are two independent live probes, so a service flapping between them can move percentage.
    expect(aliasJson.services.length).toBe(canonicalJson.services.length);
    expect(aliasJson.percentage).toBe(canonicalJson.percentage);
  });
});
