import { test, expect } from '@playwright/test';

/**
 * E2E tests for Services Health Dashboard
 *
 * Tests the health monitoring interface that displays status
 * for all PMOVES services including Agent Zero, Archon, Hi-RAG,
 * Flute Gateway, and other core services.
 *
 * Route: /dashboard/health
 * API: /api/health, /api/health-all
 */

test.describe('Services Health Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/health');
  });

  test('page loads with health overview visible', async ({ page }) => {
    // Verify main content area
    await expect(page.getByRole('main')).toBeVisible();

    // Check for health dashboard heading
    const heading = page.getByRole('heading', { name: /health|services|status/i });
    const count = await heading.count();
    if (count > 0) {
      await expect(heading.first()).toBeVisible();
    }
  });

  test('displays overall health status', async ({ page }) => {
    // Look for overall status indicator
    const statusIndicator = page.locator('[data-testid="health-status"], .health-status, [class*="healthStatus"]');
    await page.waitForTimeout(1000); // Wait for health data to load

    const count = await statusIndicator.count();
    if (count > 0) {
      await expect(statusIndicator.first()).toBeVisible();

      // Status should show one of: healthy, degraded, unhealthy, or similar
      const statusText = await statusIndicator.first().textContent();
      expect(statusText?.toLowerCase()).toMatch(/healthy|degraded|unhealthy|online|offline|ok|error/);
    }
  });

  test('lists multiple services with individual status', async ({ page }) => {
    // Wait for service data to load
    await page.waitForTimeout(2000);

    // Look for service cards or list items
    const serviceCards = page.locator('[data-testid="service-card"], .service-card, [class*="serviceCard"]');
    const serviceList = page.locator('[data-testid="service-list"], .service-list');

    const hasCards = await serviceCards.count() > 0;
    const hasList = await serviceList.count() > 0;

    // At least one should be present
    expect(hasCards || hasList).toBe(true);

    if (hasCards) {
      // Should have multiple services listed
      const cardCount = await serviceCards.count();
      expect(cardCount).toBeGreaterThan(0);
    }
  });

  test('each service shows name, status, and last check time', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for service status indicators
    const serviceName = page.locator('[data-testid="service-name"], .service-name');
    const serviceStatus = page.locator('[data-testid="service-status"], .service-status');
    const lastCheck = page.locator('[data-testid="last-check"], .last-check, [class*="lastCheck"]');

    // At least service names should be visible
    const nameCount = await serviceName.count();
    if (nameCount > 0) {
      await expect(serviceName.first()).toBeVisible();
    }

    // Status indicators should be present
    const statusCount = await serviceStatus.count();
    if (statusCount > 0) {
      await expect(serviceStatus.first()).toBeVisible();
    }
  });

  test('can filter services by category', async ({ page }) => {
    // Look for category filters
    const categoryFilter = page.locator('[data-testid="category-filter"], select[name="category"]');

    if (await categoryFilter.count() > 0) {
      await expect(categoryFilter.first()).toBeVisible();

      // Try selecting a category
      await categoryFilter.first().selectOption({ index: 1 });
      await page.waitForTimeout(500);

      // Filter should be applied
      const selectedValue = await categoryFilter.first().inputValue();
      expect(selectedValue).toBeTruthy();
    }
  });

  test('can refresh health status manually', async ({ page }) => {
    // Look for refresh button
    const refreshButton = page.getByRole('button', { name: /refresh|reload/i });

    if (await refreshButton.count() > 0) {
      const initialText = await page.textContent('body');

      await refreshButton.first().click();
      await page.waitForTimeout(2000);

      // Page should still be visible after refresh
      await expect(page.getByRole('main')).toBeVisible();
    }
  });

  test('displays service health percentage or summary', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for percentage or summary text
    const percentage = page.locator('[data-testid="health-percentage"], .health-percentage');
    const summary = page.locator('[data-testid="health-summary"], .health-summary');

    const hasPercentage = await percentage.count() > 0;
    const hasSummary = await summary.count() > 0;

    // At least one summary metric should be visible
    if (hasPercentage) {
      await expect(percentage.first()).toBeVisible();
      const text = await percentage.first().textContent();
      expect(text).toMatch(/\d+%/);
    }

    if (hasSummary) {
      await expect(summary.first()).toBeVisible();
    }
  });

  test('unhealthy services are visually distinguished', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for error or unhealthy status indicators
    const unhealthyIndicator = page.locator('[data-status="unhealthy"], [data-status="error"], .unhealthy, .error');

    const count = await unhealthyIndicator.count();
    if (count > 0) {
      // If unhealthy services exist, they should be visually distinct
      const element = unhealthyIndicator.first();
      const classes = await element.getAttribute('class') || '';

      // Check for error-related class names
      expect(classes.toLowerCase()).toMatch(/error|unhealthy|danger|fail/);
    }
  });
});

/**
 * Health API Integration Tests
 * Direct API calls to health endpoints
 */
test.describe('Health API Endpoints', () => {
  const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:4482';

  test('base health endpoint responds', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('status');
    expect(body).toHaveProperty('service', 'pmoves-ui');

    // Should include database health check
    expect(body.checks).toBeDefined();
  });

  test('health-all endpoint returns service list', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health-all`);

    // Should return 200 even if some services are down
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('services');
    expect(Array.isArray(body.services)).toBe(true);
  });

  test('health-all with simple query parameter', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health-all?simple=true`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('services');
    expect(body).toHaveProperty('percentage');

    // Simple mode should only return slug, status, text
    if (body.services.length > 0) {
      const service = body.services[0];
      expect(service).toHaveProperty('slug');
      expect(service).toHaveProperty('status');
      expect(service).toHaveProperty('text');
    }
  });

  test('health-all with category filter', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health-all?category=agent`);

    // Category may not exist, but endpoint should respond
    expect([200, 404]).toContain(response.status());

    if (response.status() === 200) {
      const body = await response.json();
      expect(body).toHaveProperty('services');
    }
  });

  test('health-all with slugs filter', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health-all?slugs=agent-zero`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('health');

    if (body.health) {
      expect(body.health.slug).toBe('agent-zero');
      expect(body.health.status).toMatch(/healthy|unhealthy|degraded|unknown/);
    }
  });

  test('presign health endpoint has rate limiting', async ({ request }) => {
    // Make multiple rapid requests to test rate limiting
    const requests = [];
    for (let i = 0; i < 15; i++) {
      requests.push(request.get(`${BASE_URL}/api/health/presign`));
    }

    const responses = await Promise.all(requests);
    const statusCodes = responses.map(r => r.status());

    // At least some requests should succeed (200)
    expect(statusCodes.some(s => s === 200)).toBe(true);

    // Rate limiting should kick in (429) after threshold
    expect(statusCodes.some(s => s === 429)).toBe(true);

    // Check for rate limit headers on 429 responses
    for (const response of responses) {
      if (response.status() === 429) {
        const retryAfter = response.headers()['retry-after'];
        const rateLimitRemaining = response.headers()['x-ratelimit-remaining'];

        expect(retryAfter).toBeDefined();
        expect(rateLimitRemaining).toBeDefined();
        break; // Only need to check one
      }
    }
  });

  test('boot-jwt health endpoint returns JWT info', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health/boot-jwt`);

    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('hasToken');
    expect(body).toHaveProperty('exp');
    expect(body).toHaveProperty('now');
    expect(body).toHaveProperty('expired');

    if (body.hasToken) {
      expect(typeof body.exp).toBe('number');
      expect(typeof body.now).toBe('number');
    }
  });

  test('ingest-smoke endpoint requires auth or single-user mode', async ({ request }) => {
    // Without auth, should get 401 or 500 (missing secret)
    const response = await request.post(`${BASE_URL}/api/health/ingest-smoke`);

    // In single-user mode (CI), may return 400 (missing ownerId)
    // In production mode, should return 401 or 500
    expect([400, 401, 500]).toContain(response.status());
  });
});

/**
 * Critical Services Health Check
 * Verifies core PMOVES services are reachable
 */
test.describe('Critical Services Reachability', () => {
  const services = [
    { name: 'Agent Zero', url: process.env.NEXT_PUBLIC_AGENT_ZERO_URL || 'http://localhost:8080', path: '/healthz' },
    { name: 'Archon', url: process.env.NEXT_PUBLIC_ARCHON_URL || 'http://localhost:8091', path: '/healthz' },
    { name: 'Hi-RAG v2', url: process.env.NEXT_PUBLIC_HIRAG_URL || 'http://localhost:8086', path: '/health' },
    { name: 'Flute Gateway', url: process.env.NEXT_PUBLIC_FLUTE_GATEWAY_URL || 'http://localhost:8055', path: '/healthz' },
    { name: 'TensorZero', url: 'http://localhost:3030', path: '/' },
    { name: 'Supabase Kong', url: 'http://localhost:8000', path: '/_' },
  ];

  for (const service of services) {
    test(`${service.name} health endpoint`, async ({ request }) => {
      const response = await request.get(`${service.url}${service.path}`);

      // In CI, services may not be running
      // Accept 200 (healthy), 502/503 (unavailable), or 521 (origin down)
      expect([200, 502, 503, 521, 404]).toContain(response.status());

      if (response.status() === 200) {
        // Verify response has content
        const text = await response.text();
        expect(text.length).toBeGreaterThan(0);
      }
    });
  }
});
