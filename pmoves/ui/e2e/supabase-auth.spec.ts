import { test, expect } from '@playwright/test';

test.describe('Supabase boot session', () => {
  test('browser client uses boot JWT when provided', async ({ page }) => {
    await page.goto('/test-supabase');
    await page.waitForFunction(() => Boolean((window as any).__PMOVES_SUPABASE_BOOT));
    const bootInfo = await page.evaluate(() => (window as any).__PMOVES_SUPABASE_BOOT);
    expect(bootInfo.hasBootJwt).toBe(true);
    // Security: authorization field removed from window object to prevent XSS token theft
    expect(bootInfo.authorization).toBeUndefined();
  });
});
