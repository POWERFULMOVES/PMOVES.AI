import { test, expect } from '@playwright/test';

const EXPECTED_BOOT_JWT =
  process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT ?? 'playwright-boot-user-jwt';

test.describe('Supabase boot session', () => {
  test('browser client uses boot JWT when provided', async ({ page }) => {
    await page.goto('/test-supabase');
    await page.waitForFunction(() => Boolean((window as any).__PMOVES_SUPABASE_BOOT));
    const bootInfo = await page.evaluate(() => (window as any).__PMOVES_SUPABASE_BOOT);
    expect(bootInfo.hasBootJwt).toBe(true);
    expect(bootInfo.authorization).toBe(`Bearer ${EXPECTED_BOOT_JWT}`);
  });
});
