import { test, expect } from '@playwright/test';

const SERVICES = [
  { slug: 'open-notebook', title: 'Open Notebook' },
  { slug: 'pmoves-yt', title: 'PMOVES.YT' },
  { slug: 'jellyfin', title: 'Jellyfin' },
  { slug: 'wger', title: 'Wger' },
  { slug: 'firefly', title: 'Firefly' },
];

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

test.describe('Services dashboard', () => {
  test('exposes navigation cards for each integration', async ({ page }) => {
    await page.goto('/dashboard/services');
    await expect(page.getByRole('heading', { name: /integration services/i })).toBeVisible();

    for (const service of SERVICES) {
      await expect(page.getByRole('link', { name: new RegExp(service.title, 'i') })).toBeVisible();
    }
  });

  for (const service of SERVICES) {
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
