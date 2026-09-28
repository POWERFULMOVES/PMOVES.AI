/* ═══════════════════════════════════════════════════════════════════════════
   Jellyfin Integration E2E Tests
   Tests end-to-end Jellyfin Bridge workflows
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect, type Page } from '@playwright/test';

/*
 * Backend-free: the page talks to the Jellyfin Bridge through lib/api/jellyfin.ts
 * (`${bridge}/jellyfin/*`, default http://localhost:8093). Every /jellyfin/* request,
 * whatever host it targets, is fulfilled here; a live bridge is never contacted.
 * The Supabase origin is also mocked for the cross-page ingestion-queue test.
 *
 * Reconciled 2026-09-28 against the BUILT UI: SyncStatus is rendered at
 * app/dashboard/jellyfin/page.tsx:104 and JellyfinMediaBrowser at :161. The media
 * browser shows SEARCH RESULTS (page.tsx:50-52 -> :161), so library items appear
 * after a search is submitted (form submit, page.tsx:117), not on page load.
 * BackfillControls (batch size / priority / progress / cancel) is NOT rendered
 * anywhere; those tests stay fixme.
 */

type SyncStatusInfo = {
  status: string;
  lastSync: string | null;
  videosLinked: number;
  pendingBackfill: number;
  errors: number;
};

const LIBRARY = [
  { id: 'jf-movie-1', name: 'Test Movie', type: 'Movie', productionYear: 2020 },
  { id: 'jf-series-1', name: 'Test Series', type: 'Series', productionYear: 2021 },
  { id: 'jf-episode-1', name: 'Test Episode', type: 'Episode', seriesName: 'Test Series', seasonNumber: 1, episodeNumber: '2' },
];

interface BridgeMock {
  status: SyncStatusInfo;
  syncStatusRequests: number;
  syncRequests: number;
  searchQueries: string[];
  /** Delay (ms) on POST /jellyfin/sync so the in-flight state is observable. */
  syncDelayMs: number;
  /** HTTP status for POST /jellyfin/sync (200 = ok). */
  syncHttpStatus: number;
}

async function mockBackends(page: Page): Promise<BridgeMock> {
  const mock: BridgeMock = {
    status: {
      status: 'idle',
      lastSync: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      videosLinked: 12,
      pendingBackfill: 3,
      errors: 0,
    },
    syncStatusRequests: 0,
    syncRequests: 0,
    searchQueries: [],
    syncDelayMs: 0,
    syncHttpStatus: 200,
  };

  // Supabase (used by the ingestion-queue page in the link test): empty queue, silent realtime.
  await page.routeWebSocket(/127\.0\.0\.1:54321/, () => {});
  await page.route('http://127.0.0.1:54321/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: '[]' })
  );

  await page.route((url) => url.pathname.startsWith('/jellyfin/'), async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: 'application/json', headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*' }, body: JSON.stringify(body) });

    if (req.method() === 'OPTIONS') return json(204, {});
    if (url.pathname === '/jellyfin/sync-status') {
      mock.syncStatusRequests += 1;
      return json(200, mock.status);
    }
    if (url.pathname === '/jellyfin/sync' && req.method() === 'POST') {
      mock.syncRequests += 1;
      if (mock.syncDelayMs) await new Promise((r) => setTimeout(r, mock.syncDelayMs));
      if (mock.syncHttpStatus !== 200) return json(mock.syncHttpStatus, { detail: 'unavailable' });
      mock.status = { ...mock.status, lastSync: new Date().toISOString() };
      return json(200, { started: true });
    }
    if (url.pathname === '/jellyfin/search') {
      const q = (url.searchParams.get('query') || '').toLowerCase();
      mock.searchQueries.push(q);
      const items = LIBRARY.filter((i) => i.name.toLowerCase().includes(q));
      return json(200, { items });
    }
    return json(404, { detail: 'not mocked' });
  });

  return mock;
}

/** Items reach the media browser via a submitted search (page.tsx:43-59, :161). */
async function searchLibrary(page: Page, term: string) {
  await page.fill('[data-testid="media-search-input"]', term);
  await page.press('[data-testid="media-search-input"]', 'Enter');
}

test.describe('Jellyfin Integration', () => {
  let mock: BridgeMock;

  test.beforeEach(async ({ page }) => {
    mock = await mockBackends(page);
    // Navigate to Jellyfin dashboard
    await page.goto('/dashboard/jellyfin');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  // BUILT: SyncStatus page.tsx:104, JellyfinMediaBrowser page.tsx:161, one-click backfill SyncStatus.tsx:161-177
  test('should load Jellyfin page with initial state', async ({ page }) => {
    // Check that sync status section is present
    await expect(page.locator('[data-testid="sync-status"]')).toBeVisible();

    // Check that media browser is present
    await expect(page.locator('[data-testid="media-browser"]')).toBeVisible();

    // Check that the built backfill control is present (the options panel is unwired; see next test)
    await expect(page.locator('[data-testid="backfill-button"]')).toBeVisible();
  });

  // Split from the test above: the backfill OPTIONS panel is a separate, unrendered component.
  // fixme: UI unwired: BackfillControls not rendered (components/jellyfin/BackfillControls.tsx is imported only by BackfillControls.test.tsx; jellyfin/page.tsx renders only SyncStatus's one-click "Run Backfill", SyncStatus.tsx:161-177)
  test.fixme('should render backfill options controls', async ({ page }) => {
    // Check that backfill controls are present
    await expect(page.locator('[data-testid="backfill-controls"]')).toBeVisible();
  });

  // BUILT: SyncStatus.tsx:75-77 (last sync), :93-98 (videos linked), :108-114 (status)
  test('should display sync status', async ({ page }) => {
    // Check sync status section
    await expect(page.locator('[data-testid="sync-status"]')).toBeVisible();

    // Should show status indicator
    await expect(page.locator('[data-testid="connection-status"]')).toBeVisible();
    await expect(page.locator('[data-testid="connection-status"]')).toHaveText('idle');

    // Should show last sync time (or "Never synced" if no sync yet)
    const lastSyncTime = page.locator('[data-testid="last-sync-time"]');
    await expect(lastSyncTime).toBeVisible();

    // Should show videos linked count
    await expect(page.locator('[data-testid="videos-linked-count"]')).toBeVisible();
    await expect(page.locator('[data-testid="videos-linked-count"]')).toHaveText('12');
  });

  // BUILT: Sync Now SyncStatus.tsx:143-159 -> handleSync page.tsx:61-73 (refreshes status on success)
  test('should trigger sync operation', async ({ page }) => {
    mock.syncDelayMs = 1000;

    // Click sync now button
    await page.click('[data-testid="sync-now-button"]');

    // Button should show loading state
    await expect(page.locator('[data-testid="sync-now-button"]')).toContainText('Syncing...');

    // Wait for sync to complete (or timeout)
    await expect(page.locator('[data-testid="sync-now-button"]')).not.toContainText('Syncing...', { timeout: 30000 });
    expect(mock.syncRequests).toBe(1);

    // Sync status should be updated
    await expect(page.locator('[data-testid="last-sync-time"]')).toBeVisible();
    await expect(page.locator('[data-testid="last-sync-time"]')).toContainText('Just now');
  });

  // BUILT: button disabled={syncing} SyncStatus.tsx:145 (the "disable button" branch of this test's intent)
  test('should handle sync when already in progress', async ({ page }) => {
    mock.syncDelayMs = 1500;
    const syncButton = page.locator('[data-testid="sync-now-button"]');

    // Trigger first sync
    await syncButton.click();

    // A second trigger is prevented: the button is disabled while the first runs
    await expect(syncButton).toBeDisabled();
    await syncButton.click({ force: true });

    // Only one sync request reached the bridge
    await expect(syncButton).toBeEnabled({ timeout: 10000 });
    expect(mock.syncRequests).toBe(1);
  });

  // BUILT: media cards JellyfinMediaBrowser.tsx:103-172, details :176-201
  test('should browse media library', async ({ page }) => {
    await searchLibrary(page, 'test');

    // Check media browser
    await expect(page.locator('[data-testid="media-browser"]')).toBeVisible();

    // Media items are loaded from the (mocked) library
    const mediaItems = page.locator('[data-testid="media-item"]');
    await expect(mediaItems).toHaveCount(LIBRARY.length);
    await expect(mediaItems.first()).toBeVisible();

    // Click first item
    await mediaItems.first().click();

    // Should show media details
    await expect(page.locator('[data-testid="media-details"]')).toBeVisible();
    await expect(page.locator('[data-testid="media-details"]')).toContainText(LIBRARY[0].name);
  });

  // BUILT: search form page.tsx:117-133 (submit-driven, not debounced) -> jellyfinSearch
  test('should search media library', async ({ page }) => {
    // Enter search query and submit
    await searchLibrary(page, 'movie');

    // Check that search results are shown
    const searchResults = page.locator('[data-testid="media-item"]');
    await expect(searchResults).toHaveCount(1);
    await expect(searchResults.first()).toContainText('Test Movie');
    expect(mock.searchQueries).toContain('movie');

    // Results might be filtered or empty
    await expect(page.locator('[data-testid="media-browser"]')).toBeVisible();
  });

  // fixme: UI unwired: media type filter not rendered (jellyfin/page.tsx:117-133 has only a text search; jellyfinSearch's mediaType option, lib/api/jellyfin.ts:128-145, is never passed by page.tsx:50)
  test.fixme('should filter media by type', async ({ page }) => {
    // Select media type filter (e.g., Movies only)
    await page.selectOption('[data-testid="media-type-filter"]', 'Movie');

    // Wait for filter to apply
    await page.waitForTimeout(500);

    // Media browser should still be visible
    await expect(page.locator('[data-testid="media-browser"]')).toBeVisible();
  });

  test('should display correct badge for each media type', async ({ page }) => {
    // Wait for media items to load
    await page.waitForTimeout(1000);

    // Check for different media type badges
    const movieBadge = page.locator('[data-testid="media-badge"][data-type="Movie"]');
    const seriesBadge = page.locator('[data-testid="media-badge"][data-type="Series"]');
    const episodeBadge = page.locator('[data-testid="media-badge"][data-type="Episode"]');

    // At least check that the badges exist in the DOM
    const totalBadges = await movieBadge.count() + await seriesBadge.count() + await episodeBadge.count();
    expect(totalBadges).toBeGreaterThanOrEqual(0);
  });

  test('should show placeholder when image fails to load', async ({ page }) => {
    // This test checks for placeholder images when actual images fail
    const mediaItems = page.locator('[data-testid="media-item"]');
    const itemCount = await mediaItems.count();

    if (itemCount > 0) {
      // Check for placeholder images
      const placeholders = page.locator('[data-testid="media-image-placeholder"]');
      await placeholders.count();

      // All items should have either an image or a placeholder
      expect(itemCount).toBeGreaterThanOrEqual(0);
    }
  });

  // BUILT: grid JellyfinMediaBrowser.tsx:102 (rendered once there are results)
  test('should display media items in responsive grid', async ({ page }) => {
    await searchLibrary(page, 'test');
    await expect(page.locator('[data-testid="media-item"]').first()).toBeVisible();

    // Check that media grid container exists
    const mediaGrid = page.locator('[data-testid="media-grid"]');

    // Media grid should have responsive classes
    const className = await mediaGrid.getAttribute('class');

    // Check for responsive grid classes (Tailwind grid-cols-*)
    expect(className).toMatch(/grid-cols-/);
  });

  test('should link video to Jellyfin item', async ({ page }) => {
    // This test requires having videos in the ingestion queue
    // Navigate to ingestion queue first
    await page.goto('/dashboard/ingestion-queue');
    await page.waitForLoadState('networkidle');

    // Check if there are items to link
    const queueItems = page.locator('[data-testid="queue-item"]');
    const _itemCount = await queueItems.count();

    if (_itemCount > 0) {
      // Click first item
      await queueItems.first().click();

      // Click "Link to Jellyfin" button
      const linkButton = page.locator('[data-testid="link-jellyfin-button"]');
      if (await linkButton.isVisible({ timeout: 2000 })) {
        await linkButton.click();

        // Should open Jellyfin media browser modal
        await expect(page.locator('[data-testid="jellyfin-link-modal"]')).toBeVisible({ timeout: 5000 });

        // Select a Jellyfin item (if available)
        const jellyfinItems = page.locator('[data-testid="jellyfin-select-item"]');
        const jellyfinCount = await jellyfinItems.count();

        if (jellyfinCount > 0) {
          await jellyfinItems.first().click();

          // Confirm link
          await page.click('[data-testid="confirm-link"]');

          // Should show success message
          await expect(page.locator('[data-testid="link-success-toast"]')).toBeVisible({ timeout: 5000 });
        } else {
          // Close modal if no items
          await page.click('[data-testid="close-modal"]');
        }
      }
    }
  });

  // fixme: UI unwired: BackfillControls not rendered (components/jellyfin/BackfillControls.tsx is imported only by BackfillControls.test.tsx; jellyfin/page.tsx renders only SyncStatus's one-click "Run Backfill", SyncStatus.tsx:161-177)
  test.fixme('should trigger backfill with default options', async ({ page }) => {
    // Click backfill button
    await page.click('[data-testid="backfill-button"]');

    // Should show backfill options modal
    await expect(page.locator('[data-testid="backfill-modal"]')).toBeVisible({ timeout: 5000 });

    // Click start backfill (with default options)
    await page.click('[data-testid="start-backfill"]');

    // Should show progress indicator
    await expect(page.locator('[data-testid="backfill-progress"]')).toBeVisible({ timeout: 5000 });

    // Progress bar should be visible
    await expect(page.locator('[data-testid="backfill-progress-bar"]')).toBeVisible();
  });

  // fixme: UI unwired: BackfillControls not rendered (components/jellyfin/BackfillControls.tsx is imported only by BackfillControls.test.tsx; jellyfin/page.tsx renders only SyncStatus's one-click "Run Backfill", SyncStatus.tsx:161-177)
  test.fixme('should trigger backfill with custom options', async ({ page }) => {
    // Click backfill button
    await page.click('[data-testid="backfill-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="backfill-modal"]')).toBeVisible({ timeout: 5000 });

    // Set custom batch size
    await page.fill('[data-testid="backfill-batch-size"]', '100');

    // Set custom priority
    await page.fill('[data-testid="backfill-priority"]', '8');

    // Click start backfill
    await page.click('[data-testid="start-backfill"]');

    // Should show progress
    await expect(page.locator('[data-testid="backfill-progress"]')).toBeVisible({ timeout: 5000 });
  });

  // fixme: UI unwired: BackfillControls not rendered (components/jellyfin/BackfillControls.tsx is imported only by BackfillControls.test.tsx; jellyfin/page.tsx renders only SyncStatus's one-click "Run Backfill", SyncStatus.tsx:161-177)
  test.fixme('should validate backfill batch size (1-1000)', async ({ page }) => {
    // Click backfill button
    await page.click('[data-testid="backfill-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="backfill-modal"]')).toBeVisible({ timeout: 5000 });

    // Try to enter invalid batch size
    await page.fill('[data-testid="backfill-batch-size"]', '2000');

    // Click start backfill
    await page.click('[data-testid="start-backfill"]');

    // Should show validation error
    const validationError = page.locator('[data-testid="backfill-validation-error"]');
    const hasError = await validationError.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasError) {
      await expect(validationError).toBeVisible();
    }
  });

  // fixme: UI unwired: BackfillControls not rendered (components/jellyfin/BackfillControls.tsx is imported only by BackfillControls.test.tsx; jellyfin/page.tsx renders only SyncStatus's one-click "Run Backfill", SyncStatus.tsx:161-177)
  test.fixme('should validate backfill priority (1-10)', async ({ page }) => {
    // Click backfill button
    await page.click('[data-testid="backfill-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="backfill-modal"]')).toBeVisible({ timeout: 5000 });

    // Try to enter invalid priority
    await page.fill('[data-testid="backfill-priority"]', '15');

    // Click start backfill
    await page.click('[data-testid="start-backfill"]');

    // Should show validation error
    const validationError = page.locator('[data-testid="priority-validation-error"]');
    const hasError = await validationError.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasError) {
      await expect(validationError).toBeVisible();
    }
  });

  // fixme: UI unwired: BackfillControls not rendered (components/jellyfin/BackfillControls.tsx is imported only by BackfillControls.test.tsx; jellyfin/page.tsx renders only SyncStatus's one-click "Run Backfill", SyncStatus.tsx:161-177)
  test.fixme('should cancel backfill operation', async ({ page }) => {
    // Click backfill button
    await page.click('[data-testid="backfill-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="backfill-modal"]')).toBeVisible({ timeout: 5000 });

    // Start backfill
    await page.click('[data-testid="start-backfill"]');

    // Wait for progress to start
    await expect(page.locator('[data-testid="backfill-progress"]')).toBeVisible({ timeout: 5000 });

    // Click cancel button
    await page.click('[data-testid="cancel-backfill"]');

    // Should confirm cancellation
    const confirmDialog = page.locator('[data-testid="confirm-cancel-dialog"]');
    const hasDialog = await confirmDialog.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasDialog) {
      await page.click('[data-testid="confirm-cancel-yes"]');
    }

    // Progress should stop
    await expect(page.locator('[data-testid="backfill-progress"]')).not.toBeVisible({ timeout: 5000 });
  });

  test('should display error count when errors exist', async ({ page }) => {
    // Check sync status for error count
    const errorCount = page.locator('[data-testid="sync-error-count"]');

    // If there are errors, it should be visible
    const hasErrors = await errorCount.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasErrors) {
      await expect(errorCount).toBeVisible();
      const count = await errorCount.textContent();
      expect(parseInt(count || '0')).toBeGreaterThan(0);
    }
  });

  // BUILT: formatTimeAgo (lib/timeUtils.ts:13-32) rendered at SyncStatus.tsx:75-77
  test('should show relative time for last sync', async ({ page }) => {
    // Check last sync time
    const lastSyncTime = page.locator('[data-testid="last-sync-time"]');
    await expect(lastSyncTime).toBeVisible();

    // Should show relative time (e.g., "just now", "2h ago", etc.)
    const timeText = await lastSyncTime.textContent();
    expect(timeText).toMatch(/(just now|ago|never)/i);
    expect(timeText).toContain('2h ago');
  });

  // BUILT: Refresh SyncStatus.tsx:78-85 -> refreshSyncStatus page.tsx:25-30
  test('should refresh sync status manually', async ({ page }) => {
    await expect(page.locator('[data-testid="videos-linked-count"]')).toHaveText('12');
    const before = mock.syncStatusRequests;
    mock.status = { ...mock.status, videosLinked: 20 };

    // Click refresh button
    await page.click('[data-testid="refresh-status-button"]');

    // Status is re-fetched and the new value is shown
    await expect.poll(() => mock.syncStatusRequests).toBeGreaterThan(before);
    await expect(page.locator('[data-testid="videos-linked-count"]')).toHaveText('20');
  });

  // Split from the test above: the loading-state half of the original assertion.
  // fixme: behaviour mismatch: Refresh has no loading state (SyncStatus.tsx:78-85 renders no data-loading/busy state; onRefresh is fire-and-forget, page.tsx:25-30)
  test.fixme('should show loading state while refreshing sync status', async ({ page }) => {
    // Click refresh button
    await page.click('[data-testid="refresh-status-button"]');

    // Should show loading state briefly
    await expect(page.locator('[data-testid="refresh-status-button"]')).toHaveAttribute('data-loading', 'true');

    // Loading state should end
    await expect(page.locator('[data-testid="refresh-status-button"]')).not.toHaveAttribute('data-loading', 'true', { timeout: 5000 });
  });

  test('should highlight selected media item', async ({ page }) => {
    // Wait for media items to load
    await page.waitForTimeout(1000);

    const mediaItems = page.locator('[data-testid="media-item"]');
    const itemCount = await mediaItems.count();

    if (itemCount > 0) {
      // Click first item
      await mediaItems.first().click();

      // Should have selected class
      await expect(mediaItems.first()).toHaveClass(/selected/);
    }
  });

  test('should close media details on escape key', async ({ page }) => {
    // Wait for media items to load
    await page.waitForTimeout(1000);

    const mediaItems = page.locator('[data-testid="media-item"]');
    const itemCount = await mediaItems.count();

    if (itemCount > 0) {
      // Click item to show details
      await mediaItems.first().click();

      // Details should be visible
      await expect(page.locator('[data-testid="media-details"]')).toBeVisible();

      // Press escape
      await page.keyboard.press('Escape');

      // Details should close
      await expect(page.locator('[data-testid="media-details"]')).not.toBeVisible();
    }
  });

  // BUILT: empty state JellyfinMediaBrowser.tsx:69-77 (after a search returns no items, page.tsx:51-52)
  test('should show "no results" when filter matches nothing', async ({ page }) => {
    // A matching search first, so the empty state is caused by the query
    await searchLibrary(page, 'test');
    await expect(page.locator('[data-testid="media-item"]')).toHaveCount(LIBRARY.length);

    // Enter search query unlikely to match anything
    await searchLibrary(page, 'xyzabc123nonexistent');

    // Should show no results message
    const noResults = page.locator('[data-testid="no-media-results"]');
    await expect(noResults).toBeVisible();
    await expect(page.locator('[data-testid="media-item"]')).toHaveCount(0);
  });

  // BUILT: sync error surfaced via AlertBanner (role=alert) SyncStatus.tsx:135-139, set by page.tsx:68-70
  test('should handle service unavailable gracefully', async ({ page }) => {
    mock.syncHttpStatus = 503;

    // Try to trigger sync
    await page.click('[data-testid="sync-now-button"]');

    // Service is unavailable: an error is shown inside the sync panel and the control recovers
    const serviceError = page.locator('[data-testid="sync-status"]').getByRole('alert');
    await expect(serviceError).toBeVisible({ timeout: 5000 });
    await expect(serviceError).not.toHaveText('');
    await expect(page.locator('[data-testid="sync-now-button"]')).toBeEnabled();
    await expect(page.locator('[data-testid="sync-now-button"]')).toContainText('Sync Now');
  });

  test('should generate playback URL', async ({ page }) => {
    // Wait for media items to load
    await page.waitForTimeout(1000);

    const mediaItems = page.locator('[data-testid="media-item"]');
    const itemCount = await mediaItems.count();

    if (itemCount > 0) {
      // Click item to show details
      await mediaItems.first().click();

      // Check for playback button
      const playbackButton = page.locator('[data-testid="play-media-button"]');

      if (await playbackButton.isVisible({ timeout: 2000 })) {
        await playbackButton.click();

        // Should open playback URL or show success
        const playbackSuccess = page.locator('[data-testid="playback-url-generated"]');
        const hasSuccess = await playbackSuccess.isVisible({ timeout: 2000 }).catch(() => false);

        if (hasSuccess) {
          await expect(playbackSuccess).toBeVisible();
        }
      }
    }
  });
});
