import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

/**
 * Backend-free Playwright config for the public room launcher on the
 * unauthenticated home page (e2e/public-launcher-visibility.spec.ts).
 *
 * Why a separate config: lib/rooms.ts resolves PMOVES_ROOM_CONFIG_DIR once, at
 * module load, inside the Next server process. A test cannot change it per
 * request, so each catalog needs its own server. Playwright starts every
 * webServer before any project runs, so this config starts two dev servers
 * (the REAL catalog and a NEGATIVE FIXTURE catalog) and binds one project to
 * each through baseURL + metadata.
 *
 * Why `next dev` directly instead of `npm run dev`: the npm script goes through
 * scripts/with-env.mjs, which loads pmoves/env.shared with override:true. That
 * would pull node-local settings (and secrets) into a hermetic test and could
 * clobber PMOVES_ROOM_CONFIG_DIR.
 *
 * Two dev servers cannot share a distDir (Next 16 takes a dev lock under it),
 * so each gets its own through PMOVES_UI_DIST_DIR (read by next.config.mjs;
 * the default '.next' is unchanged everywhere else).
 *
 * reuseExistingServer is always false: reusing whatever already listens on the
 * port would test some other checkout's code and catalog.
 *
 * Run:  npm run test:e2e:launcher
 *       (== npx playwright test -c playwright.launcher.config.ts)
 */

const HOST = '127.0.0.1';
const REAL_PORT = process.env.LAUNCHER_E2E_REAL_PORT || '4491';
const FIXTURE_PORT = process.env.LAUNCHER_E2E_FIXTURE_PORT || '4492';

// Override only for controls (e.g. replaying a historical catalog); CI uses the tracked one.
export const REAL_ROOM_DIR = path.resolve(
  process.env.LAUNCHER_E2E_REAL_ROOM_DIR || path.join(__dirname, '..', 'config', 'rooms')
);
export const FIXTURE_ROOM_DIR = path.resolve(__dirname, 'e2e', 'fixtures', 'rooms-visibility');

// Placeholder values only (same as playwright.config.ts). The home page must
// not need a reachable Supabase; the spec aborts any request that tries.
const MOCK_ENV = {
  NEXT_PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54321',
  NEXT_PUBLIC_SUPABASE_ANON_KEY: 'playwright-anon-key',
  NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT: 'playwright-boot-user-jwt',
  SUPABASE_SERVICE_ROLE_KEY: 'playwright-service-role',
  SUPABASE_URL: 'http://127.0.0.1:54321',
  SUPABASE_SERVICE_URL: 'http://127.0.0.1:54321',
  NEXT_TELEMETRY_DISABLED: '1',
};

function server(port: string, roomDir: string, distDir: string) {
  return {
    command: `npx next dev --hostname ${HOST} --port ${port}`,
    url: `http://${HOST}:${port}`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: { ...MOCK_ENV, PMOVES_ROOM_CONFIG_DIR: roomDir, PMOVES_UI_DIST_DIR: distDir },
  };
}

export default defineConfig({
  testDir: './e2e',
  testMatch: /public-launcher-visibility\.spec\.ts$/,
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-launcher' }]] : 'list',
  outputDir: 'test-results-launcher',
  webServer: [
    server(REAL_PORT, REAL_ROOM_DIR, '.next-e2e-real'),
    server(FIXTURE_PORT, FIXTURE_ROOM_DIR, '.next-e2e-fixture'),
  ],
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // Each project selects its own test with `grep`, so nothing is skipped under
  // this config: a green run means both assertions ran, and a renamed test
  // makes Playwright fail with "No tests found" instead of passing vacuously.
  projects: [
    {
      name: 'launcher-real-catalog',
      grep: /real catalog:/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://${HOST}:${REAL_PORT}` },
      metadata: { launcherCatalog: 'real', roomDir: REAL_ROOM_DIR },
    },
    {
      name: 'launcher-fixture-catalog',
      grep: /negative fixture:/,
      use: { ...devices['Desktop Chrome'], baseURL: `http://${HOST}:${FIXTURE_PORT}` },
      metadata: { launcherCatalog: 'fixture', roomDir: FIXTURE_ROOM_DIR },
    },
  ],
});
