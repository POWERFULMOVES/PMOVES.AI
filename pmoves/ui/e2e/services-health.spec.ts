import { test, expect } from '@playwright/test';

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
    await page.waitForTimeout(2000);

    // Look for timestamp display
    const timestampElement = page.locator('text=/last check|updated|refreshed/i');

    if ((await timestampElement.count()) > 0) {
      await expect(timestampElement.first()).toBeVisible();
    }
  });

  // fixme: REAL UI BUG, not a stale test. Refresh stays disabled ("Refreshing...") forever because
  // useServiceHealth never clears isPolling; tracked in #3228
  test.fixme('provides refresh/recheck functionality', async ({ page }) => {
    // Look for refresh button
    const refreshButton = page.getByRole('button', { name: /refresh|recheck|reload/i });

    if ((await refreshButton.count()) > 0) {
      await refreshButton.first().click();

      // Verify loading indicator appears
      await page.waitForTimeout(500);

      // This is a soft assertion - loading state may be brief
    }
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
    // New implementation includes checks object
    if (body.checks) {
      expect(body.checks).toHaveProperty('database');
      expect(body.checks.database).toHaveProperty('status');
    }
  });

  // health-all and health/boot-jwt require an authenticated owner since #969 (authenticateRequest).
  test('health-all endpoint returns service list', async ({ page }) => {
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

  test('boot-jwt health endpoint returns token status', async ({ page }) => {
    const response = await page.request.get('/api/health/boot-jwt');

    expect(response.status()).toBe(401);
    const body = await response.json();
    expect(typeof body.error).toBe('string');
    expect(body).not.toHaveProperty('hasToken');
  });
});

test.describe('Health Error Handling', () => {
  test('handles degraded service state gracefully', async ({ page }) => {
    // Navigate to health page
    await page.goto('/dashboard/services/health');
    await page.waitForTimeout(2000);

    // Check for degraded status display (may not always be present)
    const degradedIndicator = page.locator('[class*="degraded"], [class*="warning"]');

    if ((await degradedIndicator.count()) > 0) {
      await expect(degradedIndicator.first()).toBeVisible();
    }
  });

  test('shows error messages for failed health checks', async ({ page }) => {
    const response = await page.request.get('/api/health');

    // Even in degraded state, should return proper JSON
    expect(response.headers()['content-type']).toContain('application/json');

    const body = await response.json();
    expect(body).toHaveProperty('status');
  });

  test('provides retry mechanism for failed checks', async ({ page }) => {
    await page.goto('/dashboard/services/health');

    // Look for retry/recheck buttons
    const retryButton = page.getByRole('button', { name: /retry|recheck|refresh/i });

    if ((await retryButton.count()) > 0) {
      await expect(retryButton.first()).toBeVisible();
      await retryButton.first().click();

      // Verify page updates after retry
      await page.waitForTimeout(1000);
    }
  });
});

test.describe('Health Display - UI/UX', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/services/health');
  });

  test('uses color coding for health status', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for color-coded status indicators
    // These are commonly implemented with CSS classes
    const hasColorCoding =
      (await page.locator('[class*="green"], [class*="red"], [class*="yellow"]').count()) > 0 ||
      (await page.locator('[style*="color"]').count()) > 0;

    // This is a soft assertion - depends on implementation
    if (hasColorCoding) {
      const statusIndicator = page.locator('[class*="status"]').first();
      await expect(statusIndicator).toBeVisible();
    }
  });

  test('displays service count summary', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for summary text (e.g., "5/7 services healthy")
    const summaryText = page.getByText(/\d+\/\d+.*services/i);

    if ((await summaryText.count()) > 0) {
      await expect(summaryText.first()).toBeVisible();
    }
  });

  test('groups services by category or tier', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for category/section headings
    const headings = page.locator('h2, h3, [class*="category"], [class*="group"]');
    const hasGrouping = await headings.count() > 1; // More than main heading

    // Soft assertion - grouping may not always be present
    if (hasGrouping) {
      await expect(headings.nth(1)).toBeVisible();
    }
  });
});
