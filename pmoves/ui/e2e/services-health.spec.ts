import { test, expect, type Page } from '@playwright/test';

/**
 * E2E Tests for Service Health Validation
 *
 * Tests the health monitoring interface for:
 * - Service health status display
 * - Health check indicators
 * - Service detail pages
 * - Degraded service handling
 *
 * @module e2e/services-health
 */

// Services that should have health checks
// `title` is what the detail page renders; `view` is which branch of
// app/dashboard/services/[service]/page.tsx serves it: 'guide' = markdown runbook
// (lib/services.ts), 'catalog' = CatalogFallback (lib/serviceCatalog.ts).
const CORE_SERVICES = [
  { name: 'Hi-RAG v2', slug: 'hi-rag-gateway-v2', title: 'Hi-RAG v2 CPU', view: 'catalog', port: 8086 },
  { name: 'Agent Zero', slug: 'agent-zero', title: 'Agent Zero', view: 'guide', port: 8080 },
  { name: 'Archon', slug: 'archon', title: 'Archon', view: 'guide', port: 8091 },
  { name: 'Flute Gateway', slug: 'flute-gateway', port: 8055 },
  { name: 'TensorZero', slug: 'tensorzero', port: 3030 },
  { name: 'DeepResearch', slug: 'deepresearch', port: 8098 },
  { name: 'Jellyfin Bridge', slug: 'jellyfin-bridge', port: 8093 },
];

test.describe('Services Health Dashboard', () => {
  // There is no /dashboard/services/health route (it renders 404); health monitoring lives on
  // the services dashboard itself ("Full service catalog with real-time health monitoring").
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/services');
  });

  test('displays health dashboard with all core services', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Services', exact: true }).first()).toBeVisible();

    // Every service card carries a health indicator
    const indicators = page.getByTestId('service-health-indicator');
    await expect(indicators.first()).toBeVisible();
    expect(await indicators.count()).toBeGreaterThan(3);
  });

  test('shows health status indicators (healthy/unhealthy/degraded)', async ({ page }) => {
    const indicators = page.getByTestId('service-health-indicator');
    await expect(indicators.first()).toBeVisible();

    // Each indicator exposes its state; with no backend reachable the state is 'unknown'.
    const statuses = await indicators.evaluateAll((els) => els.map((e) => e.getAttribute('data-status')));
    expect(statuses.length).toBeGreaterThan(0);
    for (const s of statuses) {
      expect(s).toMatch(/^(healthy|unhealthy|degraded|unknown|checking)$/);
    }
  });

  test('provides service detail navigation', async ({ page }) => {
    // Service cards link to their detail page; pick the first card that has a health indicator
    const card = page
      .locator('a[href^="/dashboard/services/"]')
      .filter({ has: page.getByTestId('service-health-indicator') })
      .first();
    await expect(card).toBeVisible();
    const href = await card.getAttribute('href');
    await card.click();

    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(page.getByTestId('service-title')).toBeVisible();
  });

  test('shows last check timestamp', async ({ page }) => {
    // SystemStatsBar renders "Updated <n>s ago" only once useServiceHealth has a successful
    // /api/services-hub response carrying health.services (lib/useServiceHealth.ts sets lastUpdate
    // there). Seed that response so the assertion is deterministic without a backend.
    await page.route('**/api/services-hub*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          health: { services: [{ slug: 'agent-zero', status: 'healthy', responseTime: 12 }] },
        }),
      })
    );
    await page.reload();

    await expect(page.getByText(/^Updated \d+(s|m|h) ago$/)).toBeVisible();
  });

  // fixme: REAL UI BUG, not a stale test. Refresh stays disabled ("Refreshing...") forever because
  // useServiceHealth never clears isPolling; tracked in #3228
  test.fixme('provides refresh/recheck functionality', async ({ page }) => {
    // Once #3228 is fixed the button must settle back to an enabled "Refresh" after the first check,
    // and a click must show the in-flight state.
    const refreshButton = page.getByRole('button', { name: /^refresh$/i });
    await expect(refreshButton).toBeEnabled();
    await refreshButton.click();
    await expect(page.getByRole('button', { name: /refreshing/i })).toBeVisible();
  });
});

test.describe('Individual Service Health', () => {
  for (const service of CORE_SERVICES.slice(0, 3)) {
    // Test a subset of services to keep tests fast
    test.describe(`${service.name}`, () => {
      test('shows service health details', async ({ page }) => {
        await page.goto(`/dashboard/services/${service.slug}`);

        await expect(page.getByTestId('service-title')).toHaveText(service.title ?? service.name);
        const body = service.view === 'guide' ? 'service-guide' : 'service-catalog-fallback';
        await expect(page.getByTestId(body)).toBeVisible();
      });

      test('displays service endpoint information', async ({ page }) => {
        await page.goto(`/dashboard/services/${service.slug}`);

        if (service.view === 'catalog') {
          // CatalogFallback lists registered endpoints (or says none are registered)
          const fallback = page.getByTestId('service-catalog-fallback');
          await expect(fallback.getByRole('heading', { name: 'Endpoints' })).toBeVisible();
        } else {
          // Runbook services render their markdown guide, which documents the endpoints
          await expect(page.getByTestId('service-guide')).not.toBeEmpty();
        }
      });

      test('shows service-specific metrics', async ({ page }) => {
        await page.goto(`/dashboard/services/${service.slug}`);

        if (service.view === 'catalog') {
          // Service Overview <dl>: slug, category, profile, health check
          const fallback = page.getByTestId('service-catalog-fallback');
          await expect(fallback.locator('dl')).toBeVisible();
          await expect(fallback.locator('dd').first()).toHaveText(service.slug);
        } else {
          await expect(page.getByTestId('service-guide')).toBeVisible();
        }
      });
    });
  }
});

test.describe('Health API Endpoints', () => {
  // @backend tests need a live stack (Supabase reachable from the UI server); /api/health answers 503
  // without one. Excluded from the default CI run by `--grep-invert @backend` (see package.json
  // "test:e2e"). Run them against a live stack with: npm run test:e2e:backend
  test('base health endpoint returns JSON response', { tag: '@backend' }, async ({ page }) => {
    const response = await page.request.get('/api/health');

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('status');
    expect(body.status).toMatch(/healthy|degraded|unhealthy/);
  });

  test('health endpoint includes database check', { tag: '@backend' }, async ({ page }) => {
    const response = await page.request.get('/api/health');

    expect(response.status()).toBeLessThan(500);

    const body = await response.json();
    // app/api/health/route.ts always returns checks.database (it probes Supabase)
    expect(body).toHaveProperty('checks.database.status');
    expect(body.checks.database.status).toMatch(/healthy|unhealthy/);
  });

  // health-all and health/boot-jwt require an authenticated owner since #969 (authenticateRequest).
  // The default run has no session, so these two tests cover ONLY the auth gate. The success
  // shapes are asserted by the ORIGINAL tests (same names as on main), restored in the
  // 'authenticated' @backend describe block below.
  test('health-all endpoint refuses unauthenticated requests', async ({ page }) => {
    const response = await page.request.get('/api/health-all?simple=true');

    // Unauthenticated: refused with 401 and a JSON error, no service list leaked
    expect(response.status()).toBe(401);
    const body = await response.json();
    expect(typeof body.error).toBe('string');
    expect(body).not.toHaveProperty('services');
  });

  test('presign health endpoint returns service status', async ({ page }) => {
    const response = await page.request.get('/api/health/presign');

    expect(response.status()).toBeLessThan(500);

    const body = await response.json();
    expect(body).toHaveProperty('service');
    expect(body.service).toBe('presign-health');
  });

  test('boot-jwt health endpoint refuses unauthenticated requests', async ({ page }) => {
    const response = await page.request.get('/api/health/boot-jwt');

    expect(response.status()).toBe(401);
    const body = await response.json();
    expect(typeof body.error).toBe('string');
    expect(body).not.toHaveProperty('hasToken');
  });

  /**
   * Success shapes of the owner-gated routes, restored from origin/main with their original names
   * and assertions. Needs a live stack AND a session: auth comes from the E2E_AUTH_TOKEN
   * environment variable (a Supabase-issued access token, i.e. a JWT with a `sub` claim), sent as
   * `Authorization: Bearer`, which authenticateRequest() reads first. Without it these SKIP with
   * that message; none passes vacuously and none fails for want of credentials.
   *
   *   E2E_AUTH_TOKEN=<access token> npm run test:e2e:backend
   */
  test.describe('authenticated', { tag: '@backend' }, () => {
    const token = process.env.E2E_AUTH_TOKEN;
    test.skip(
      !token,
      'E2E_AUTH_TOKEN is not set: owner-gated routes need a Supabase access token (Bearer JWT with a sub claim)'
    );
    const headers = () => ({ Authorization: `Bearer ${token}` });

    test('health-all endpoint returns service list', async ({ page }) => {
      const response = await page.request.get('/api/health-all?simple=true', { headers: headers() });

      expect(response.status()).toBe(200);

      const body = await response.json();
      expect(body).toHaveProperty('services');
      expect(Array.isArray(body.services)).toBe(true);
    });

    test('boot-jwt health endpoint returns token status', async ({ page }) => {
      const response = await page.request.get('/api/health/boot-jwt', { headers: headers() });

      expect(response.status()).toBe(200);

      const body = await response.json();
      expect(body).toHaveProperty('hasToken');
      expect(typeof body.hasToken).toBe('boolean');
    });
  });
});

/**
 * Serve a fixed /api/services-hub health payload (the only fetch useServiceHealth makes), so the
 * services dashboard renders deterministic health state without a backend.
 */
async function mockServicesHub(
  page: Page,
  services: Array<{ slug: string; status: string; responseTime?: number }>
) {
  await page.route('**/api/services-hub*', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ health: { services } }),
    })
  );
}

// Retargeted 2026-09-28 from /dashboard/services/health, which has never existed (it renders 404),
// to /dashboard/services, where health monitoring actually lives.
test.describe('Health Error Handling', () => {
  // fixme: FEATURE NOT BUILT: there is no degraded health state. ServiceHealthStatus is
  // 'healthy' | 'unhealthy' | 'unknown' | 'checking' (lib/serviceHealth.ts:9) and
  // ServiceHealthIndicator has no degraded style (components/services/ServiceHealthIndicator.tsx:33-38),
  // so a degraded service falls into the "unknown" count. The body states the intended behaviour.
  test.fixme('handles degraded service state gracefully', async ({ page }) => {
    await mockServicesHub(page, [{ slug: 'prometheus', status: 'degraded', responseTime: 900 }]);
    await page.goto('/dashboard/services');

    const indicator = page.locator('[data-testid="service-health-indicator"][data-status="degraded"]');
    await expect(indicator).toBeVisible();
    await expect(page.getByText(/1 degraded/)).toBeVisible();
  });

  test('shows error messages for failed health checks', async ({ page }) => {
    const response = await page.request.get('/api/health');

    // Even in degraded state, should return proper JSON
    expect(response.headers()['content-type']).toContain('application/json');

    const body = await response.json();
    expect(body).toHaveProperty('status');
  });

  // fixme: REAL UI BUG #3228. The Refresh button is the retry mechanism, but it stays disabled
  // ("Refreshing...") forever: useServiceHealth sets isPolling true on mount and never clears it
  // (lib/useServiceHealth.ts:106), and SystemStatsBar disables the button while isChecking
  // (components/hub/SystemStatsBar.tsx:117).
  test.fixme('provides retry mechanism for failed checks', async ({ page }) => {
    await mockServicesHub(page, [{ slug: 'postgres', status: 'unhealthy' }]);
    await page.goto('/dashboard/services');

    const refresh = page.getByRole('button', { name: /^refresh$/i });
    await expect(refresh).toBeEnabled();
    const recheck = page.waitForRequest('**/api/services-hub*');
    await refresh.click();
    await recheck;
  });
});

test.describe('Health Display - UI/UX', () => {
  test('uses color coding for health status', async ({ page }) => {
    await mockServicesHub(page, [
      { slug: 'prometheus', status: 'healthy', responseTime: 10 },
      { slug: 'postgres', status: 'unhealthy' },
    ]);
    await page.goto('/dashboard/services');

    const byStatus = (s: string) =>
      page.locator(`[data-testid="service-health-indicator"][data-status="${s}"]`);
    // Each state maps to its own colour class (components/services/ServiceHealthIndicator.tsx:33-38)
    await expect(byStatus('healthy').first()).toHaveClass(/bg-cata-forest/);
    await expect(byStatus('unhealthy').first()).toHaveClass(/bg-cata-ember/);
    await expect(byStatus('unknown').first()).toHaveClass(/bg-ink-muted/);
  });

  test('displays service count summary', async ({ page }) => {
    await mockServicesHub(page, [
      { slug: 'prometheus', status: 'healthy', responseTime: 10 },
      { slug: 'grafana', status: 'healthy', responseTime: 12 },
      { slug: 'postgres', status: 'unhealthy' },
    ]);
    await page.goto('/dashboard/services');

    const summary = page.getByLabel('System health status');
    await expect(summary.getByText('2 healthy', { exact: true })).toBeVisible();
    await expect(summary.getByText('1 down', { exact: true })).toBeVisible();

    // unknown = total - healthy - down, where total is the whole catalog
    const totalText = await summary.getByText(/^of \d+ services$/).textContent();
    const total = Number(totalText?.match(/\d+/)?.[0]);
    expect(total).toBeGreaterThan(3);
    await expect(summary.getByText(`${total - 3} unknown`, { exact: true })).toBeVisible();
  });

  test('groups services by category or tier', async ({ page }) => {
    await page.goto('/dashboard/services');

    const cards = page.locator('a.card-brutal');
    await expect(cards.first()).toBeVisible();
    const allCount = await cards.count();

    await page.getByRole('button', { name: 'Filter by Database' }).click();
    await expect(page.getByRole('button', { name: 'Filter by Database' })).toHaveAttribute('aria-pressed', 'true');

    // The filter narrows the grid, and every remaining card is tagged with the chosen category
    await expect.poll(() => cards.count()).toBeLessThan(allCount);
    const categories = await cards.evaluateAll((els) =>
      els.map((el) => el.querySelector('span')?.textContent?.trim())
    );
    expect(categories.length).toBeGreaterThan(0);
    for (const c of categories) expect(c).toBe('database');
  });
});
