import { test, expect } from '@playwright/test';

// TAC 1: Services to check for visibility on the centralized catalog page
const SERVICES = [
  { slug: 'pmoves-yt', title: 'PMOVES.YT' },
  { slug: 'jellyfin-bridge', title: 'Jellyfin Bridge' },
  { slug: 'flute-gateway', title: 'Flute Gateway' },
  { slug: 'agent-zero', title: 'Agent Zero' },
  { slug: 'archon', title: 'Archon' },
];

// Services with markdown documentation pages (legacy INTEGRATION_SERVICES)
const DOCUMENTED_SERVICES = [
  { slug: 'pmoves-yt', title: 'PMOVES.YT' },
];

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

test.describe('Services dashboard', () => {
  test('exposes navigation cards for each integration', async ({ page }) => {
    await page.goto('/dashboard/services');
    // TAC 1: The centralized UI uses "Services" as the page title
    await expect(page.getByRole('heading', { name: /services/i })).toBeVisible();

    // Use .first() since new design has multiple links per service (card + quick links)
    for (const service of SERVICES) {
      await expect(page.getByRole('link', { name: new RegExp(service.title, 'i') }).first()).toBeVisible();
    }
  });

  // Only test documented services for markdown rendering
  for (const service of DOCUMENTED_SERVICES) {
    test(`renders the ${service.title} runbook without redirecting to login`, async ({ page }) => {
      await page.goto(`/dashboard/services/${service.slug}`);
      const headingMatcher = new RegExp(`^${escapeRegExp(service.title)}$`, 'i');
      await expect(
        page.getByRole('heading', { level: 1, name: headingMatcher })
      ).toBeVisible();
      await expect(page.locator('header').first()).toContainText(service.title);
      await expect(page.locator('article')).toBeVisible();
      await expect(
        page.getByRole('navigation').getByRole('link', { name: /services/i })
      ).toBeVisible();
      await expect(page.getByRole('link', { name: /login/i })).toHaveCount(0);
    });
  }
});
