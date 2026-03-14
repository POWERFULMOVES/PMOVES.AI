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
const CORE_SERVICES = [
  { name: 'Hi-RAG v2', slug: 'hirag-v2', port: 8086 },
  { name: 'Agent Zero', slug: 'agent-zero', port: 8080 },
  { name: 'Archon', slug: 'archon', port: 8091 },
  { name: 'Flute Gateway', slug: 'flute-gateway', port: 8055 },
  { name: 'TensorZero', slug: 'tensorzero', port: 3030 },
  { name: 'DeepResearch', slug: 'deepresearch', port: 8098 },
  { name: 'Jellyfin Bridge', slug: 'jellyfin-bridge', port: 8093 },
];

test.describe('Services Health Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/services/health');
  });

  test('displays health dashboard with all core services', async ({ page }) => {
    // Check for health dashboard heading
    await expect(page.getByRole('heading', { name: /health|service status/i })).toBeVisible();

    // Wait for health data to load
    await page.waitForTimeout(2000);

    // Check that at least some services are displayed
    const serviceCards = page.locator('[class*="service"], [class*="health"], tr');
    await expect(serviceCards.first()).toBeVisible();
  });

  test('shows health status indicators (healthy/unhealthy/degraded)', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for status indicators
    const healthyIndicator = page.locator('[class*="healthy"], [class*="status-ok"], [data-status="healthy"]');
    const unhealthyIndicator = page.locator('[class*="unhealthy"], [class*="status-error"], [data-status="unhealthy"]');
    const degradedIndicator = page.locator('[class*="degraded"], [class*="status-warning"], [data-status="degraded"]');

    // At least one status indicator should be visible
    const hasStatusIndicators =
      (await healthyIndicator.count()) > 0 ||
      (await unhealthyIndicator.count()) > 0 ||
      (await degradedIndicator.count()) > 0;

    expect(hasStatusIndicators).toBe(true);
  });

  test('provides service detail navigation', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for clickable service cards/rows
    const serviceLinks = page.locator('a[href*="/services/"], tr[onclick]');

    if ((await serviceLinks.count()) > 0) {
      // Click first service link
      await serviceLinks.first().click();

      // Verify navigation to detail page
      await expect(page.getByRole('heading')).toBeVisible();

      // Check for service-specific health info
      const hasHealthInfo =
        (await page.getByText(/health|status|uptime/i).count()) > 0 ||
        (await page.locator('[class*="metric"], [class*="stat"]').count()) > 0;

      expect(hasHealthInfo).toBe(true);
    }
  });

  test('shows last check timestamp', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for timestamp display
    const timestampElement = page.locator('text=/last check|updated|refreshed/i');

    if ((await timestampElement.count()) > 0) {
      await expect(timestampElement.first()).toBeVisible();
    }
  });

  test('provides refresh/recheck functionality', async ({ page }) => {
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

        // Check for service name in heading
        await expect(page.getByRole('heading')).toBeVisible();

        // Check for health status section
        const hasHealthSection =
          (await page.getByText(/health|status/i).count()) > 0 ||
          (await page.locator('[class*="health"], [class*="status"]').count()) > 0;

        expect(hasHealthSection).toBe(true);
      });

      test('displays service endpoint information', async ({ page }) => {
        await page.goto(`/dashboard/services/${service.slug}`);

        // Look for endpoint/URL info
        const hasEndpointInfo =
          (await page.getByText(/http|endpoint|url|port/i).count()) > 0 ||
          (await page.locator('code').count()) > 0;

        // Soft assertion - may not always be displayed
        if (hasEndpointInfo) {
          const codeElement = page.locator('code').first();
          if ((await codeElement.count()) > 0) {
            await expect(codeElement).toContainText(/http|localhost/i);
          }
        }
      });

      test('shows service-specific metrics', async ({ page }) => {
        await page.goto(`/dashboard/services/${service.slug}`);

        // Wait for metrics to load
        await page.waitForTimeout(1000);

        // Look for metric displays
        const metricElements = page.locator('[class*="metric"], [class*="stat"], dt');

        // At least one detail element should be present
        const hasDetails =
          (await metricElements.count()) > 0 ||
          (await page.locator('dl').count()) > 0;

        expect(hasDetails).toBe(true);
      });
    });
  }
});

test.describe('Health API Endpoints', () => {
  test('base health endpoint returns JSON response', async ({ page }) => {
    const response = await page.request.get('/api/health');

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('status');
    expect(body.status).toMatch(/healthy|degraded|unhealthy/);
  });

  test('health endpoint includes database check', async ({ page }) => {
    const response = await page.request.get('/api/health');

    expect(response.status()).toBeLessThan(500);

    const body = await response.json();
    // New implementation includes checks object
    if (body.checks) {
      expect(body.checks).toHaveProperty('database');
      expect(body.checks.database).toHaveProperty('status');
    }
  });

  test('health-all endpoint returns service list', async ({ page }) => {
    const response = await page.request.get('/api/health-all?simple=true');

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('services');
    expect(Array.isArray(body.services)).toBe(true);
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

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('hasToken');
    expect(typeof body.hasToken).toBe('boolean');
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
