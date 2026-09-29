import { test, expect } from '@playwright/test';

test.describe('Supabase boot session', () => {
  // Rewritten 2026-09-28 (lane test/e2e-reconcile-open-jev). The original test waited for
  // window.__PMOVES_SUPABASE_BOOT, which cbf69c3fe (2026-08-06, cookie-based SSR auth) removed.
  // The current contract is the security half of the old test: nothing about the boot JWT is on window.
  // renamed-from: browser client uses boot JWT when provided
  test('boot JWT is never exposed on window', async ({ page }) => {
    await page.goto('/test-supabase');
    await expect(page.getByRole('heading', { name: 'Supabase diagnostics' })).toBeVisible();

    const exposed = await page.evaluate(() => {
      const w = window as unknown as Record<string, unknown>;
      return {
        bootGlobal: w.__PMOVES_SUPABASE_BOOT,
        jwtOnWindow: Object.keys(w).filter((k) => /boot.*jwt|jwt.*boot/i.test(k)),
      };
    });
    expect(exposed.bootGlobal).toBeUndefined();
    expect(exposed.jwtOnWindow).toEqual([]);
  });
});
