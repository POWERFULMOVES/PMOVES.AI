/* ═══════════════════════════════════════════════════════════════════════════
   Enhanced Video Approval E2E Tests
   Tests end-to-end ingestion queue bulk approval workflows
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect, type Page } from '@playwright/test';

/*
 * Backend-free: the page reads/writes the ingestion queue through supabase-js
 * (lib/realtimeClient.ts fetchIngestionQueue / approveIngestion / rejectIngestion)
 * against NEXT_PUBLIC_SUPABASE_URL (playwright.config.ts -> 127.0.0.1:54321).
 * Every REST/RPC call is fulfilled here and the realtime websocket is routed to
 * a silent mock, so no live Supabase is ever contacted.
 *
 * Reconciled 2026-09-28 against the BUILT UI:
 *   - BulkApprovalActions is rendered at app/dashboard/ingestion-queue/page.tsx:447
 *     and only renders once something is selected (BulkApprovalActions.tsx:104-107),
 *     so selection controls are reached by selecting a row first, as a user would.
 *   - ApprovalRulesConfig is an INLINE panel behind the "Approval Rules" toggle
 *     (page.tsx:351-361 -> :379-387), not a modal; the rule editor IS a modal
 *     (ApprovalRulesConfig.tsx:383-608).
 *   - The built UI has no success toasts. Success is observed as the built UI
 *     signals it: the RPC is called with the chosen arguments and the selection
 *     is cleared (BulkApprovalActions.tsx:82-94, page.tsx:236/254); a saved rule
 *     closes the editor and appears in the rules list (ApprovalRulesConfig.tsx:177-184, :307).
 */

const SUPABASE_ORIGIN = 'http://127.0.0.1:54321';

type QueueItem = {
  id: string;
  owner_id: null;
  source_type: string;
  source_url: string | null;
  source_id: string | null;
  title: string | null;
  description: string | null;
  thumbnail_url: null;
  duration_seconds: number | null;
  source_meta: Record<string, unknown>;
  status: string;
  priority: number;
  approved_by: null;
  approved_at: null;
  rejection_reason: null;
  processor_id: null;
  processing_started_at: null;
  processed_at: null;
  error_message: string | null;
  retry_count: number;
  output_refs: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

function makeItem(n: number, status: string, sourceType: string, title: string): QueueItem {
  const ts = new Date(Date.now() - n * 60_000).toISOString();
  return {
    id: `00000000-0000-4000-8000-00000000000${n}`,
    owner_id: null,
    source_type: sourceType,
    source_url: `https://example.test/item-${n}`,
    source_id: null,
    title,
    description: null,
    thumbnail_url: null,
    duration_seconds: 600,
    source_meta: { channel_name: 'TED' },
    status,
    priority: 0,
    approved_by: null,
    approved_at: null,
    rejection_reason: null,
    processor_id: null,
    processing_started_at: null,
    processed_at: null,
    error_message: null,
    retry_count: 0,
    output_refs: {},
    created_at: ts,
    updated_at: ts,
  };
}

// Two pending (the default filter), plus non-pending items visible under "All".
const FIXTURE: QueueItem[] = [
  makeItem(1, 'pending', 'youtube', 'Pending Video One'),
  makeItem(2, 'pending', 'pdf', 'Pending Paper Two'),
  makeItem(3, 'approved', 'youtube', 'Approved Video Three'),
  makeItem(4, 'completed', 'url', 'Completed Page Four'),
];

type RpcCall = { fn: string; body: Record<string, unknown> };

interface QueueMock {
  rpcCalls: RpcCall[];
  queueRequests: string[];
  /** Delay (ms) applied to approve/reject RPC responses, to observe processing state. */
  rpcDelayMs: number;
}

const CORS = { 'access-control-allow-origin': '*' };

async function mockSupabase(page: Page): Promise<QueueMock> {
  const mock: QueueMock = { rpcCalls: [], queueRequests: [], rpcDelayMs: 0 };

  // Realtime: accept the socket, never forward it to a server.
  await page.routeWebSocket(/127\.0\.0\.1:54321/, () => {});

  await page.route(`${SUPABASE_ORIGIN}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (req.method() === 'OPTIONS') {
      await route.fulfill({
        status: 204,
        headers: { ...CORS, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' },
      });
      return;
    }
    if (url.pathname === '/rest/v1/ingestion_queue') {
      mock.queueRequests.push(url.search);
      const status = url.searchParams.get('status')?.replace(/^eq\./, '');
      const sourceType = url.searchParams.get('source_type')?.replace(/^eq\./, '');
      const rows = FIXTURE.filter(
        (i) => (!status || i.status === status) && (!sourceType || i.source_type === sourceType)
      );
      await route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify(rows) });
      return;
    }
    const rpc = url.pathname.match(/^\/rest\/v1\/rpc\/(approve_ingestion|reject_ingestion)$/);
    if (rpc) {
      const body = JSON.parse(req.postData() || '{}') as Record<string, unknown>;
      mock.rpcCalls.push({ fn: rpc[1], body });
      if (mock.rpcDelayMs) await new Promise((r) => setTimeout(r, mock.rpcDelayMs));
      const item = FIXTURE.find((i) => i.id === body.p_id) ?? null;
      await route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify(item) });
      return;
    }
    await route.fulfill({ status: 404, contentType: 'application/json', headers: CORS, body: '{}' });
  });

  return mock;
}

const pendingIds = FIXTURE.filter((i) => i.status === 'pending').map((i) => i.id);

/** The bulk bar (and its selection controls) renders only once a row is selected. */
async function selectFirstThenAllVisible(page: Page) {
  await page.check('[data-testid="select-item-0"]');
  await page.click('[data-testid="select-all-visible"]');
  await expect(page.locator('[data-testid="selected-count"]')).toContainText(`${pendingIds.length} items selected`);
}

async function openRulesPanel(page: Page) {
  await page.click('[data-testid="approval-rules-button"]');
  await expect(page.locator('[data-testid="approval-rules-panel"]')).toBeVisible({ timeout: 5000 });
}

async function openNewRuleEditor(page: Page) {
  await openRulesPanel(page);
  await page.click('[data-testid="new-rule-button"]');
  await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });
}

/** Saving closes the editor and lists the rule; returns the new list item. */
async function saveRuleAndExpectListed(page: Page, name: string) {
  await page.click('[data-testid="save-rule"]');
  await expect(page.locator('[data-testid="rule-editor-modal"]')).not.toBeVisible();
  const item = page.locator('[data-testid="approval-rule-item"]').filter({ hasText: name });
  await expect(item).toHaveCount(1);
  return item;
}

test.describe('Enhanced Video Approval', () => {
  let mock: QueueMock;

  test.beforeEach(async ({ page }) => {
    mock = await mockSupabase(page);
    // Navigate to ingestion queue
    await page.goto('/dashboard/ingestion-queue');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  // BUILT: queue list container page.tsx:458; bulk bar hidden until selection (BulkApprovalActions.tsx:104-107)
  test('should load ingestion queue with initial state', async ({ page }) => {
    // Check that queue table is present
    await expect(page.locator('[data-testid="ingestion-queue-table"]')).toBeVisible();
    await expect(page.locator('[data-testid="queue-item"]')).toHaveCount(pendingIds.length);

    // Bulk actions bar is not rendered while nothing is selected
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).toHaveCount(0);
  });

  test('should display queue items with correct status', async ({ page }) => {
    // Check for queue items
    const queueItems = page.locator('[data-testid="queue-item"]');
    await expect(queueItems).toHaveCount(pendingIds.length);
    await expect(queueItems.first()).toBeVisible();

    // Check for status badges (default filter is "pending", page.tsx:67)
    const statusBadges = page.locator('[data-testid="status-badge"]');
    await expect(statusBadges).toHaveCount(pendingIds.length);
    await expect(statusBadges.first()).toHaveText('pending');
  });

  test('should select single item', async ({ page }) => {
    const queueItems = page.locator('[data-testid="queue-item"]');
    await expect(queueItems).toHaveCount(pendingIds.length);

    // Click checkbox on first item
    await page.check('[data-testid="select-item-0"]');

    // Checkbox should be checked
    await expect(page.locator('[data-testid="select-item-0"]')).toBeChecked();

    // Bulk actions bar should appear
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).toBeVisible();
  });

  test('should bulk select multiple items', async ({ page }) => {
    const queueItems = page.locator('[data-testid="queue-item"]');
    await expect(queueItems).toHaveCount(2);

    // Select multiple items
    await page.check('[data-testid="select-item-0"]');
    await page.check('[data-testid="select-item-1"]');

    // Bulk actions bar should be visible
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).toBeVisible();

    // Should show correct count
    await expect(page.locator('[data-testid="selected-count"]')).toContainText('2 items selected');
  });

  // BUILT: BulkApprovalActions.tsx:125-131, shown once a row is selected (:104-107)
  test('should show "select all visible" button', async ({ page }) => {
    await page.check('[data-testid="select-item-0"]');
    await expect(page.locator('[data-testid="select-all-visible"]')).toBeVisible();
  });

  // BUILT: BulkApprovalActions.tsx:132-138, shown once a row is selected (:104-107)
  test('should show "select pending" button', async ({ page }) => {
    await page.check('[data-testid="select-item-0"]');
    await expect(page.locator('[data-testid="select-pending"]')).toBeVisible();
  });

  // BUILT: handleSelectVisible BulkApprovalActions.tsx:62-66
  test('should select all visible items', async ({ page }) => {
    // Click select all visible
    await selectFirstThenAllVisible(page);

    // All visible checkboxes should be checked
    const checkboxes = page.locator('[data-testid^="select-item-"]');
    const count = await checkboxes.count();
    expect(count).toBe(pendingIds.length);

    for (let i = 0; i < count; i++) {
      const checkbox = checkboxes.nth(i);
      await expect(checkbox).toBeVisible();
      await expect(checkbox).toBeChecked();
    }
  });

  // BUILT: handleSelectPending BulkApprovalActions.tsx:68-71
  test('should select only pending items', async ({ page }) => {
    // Show every status so non-pending rows are present
    await page.selectOption('[data-testid="queue-status-filter"]', 'all');
    await expect(page.locator('[data-testid="queue-item"]')).toHaveCount(FIXTURE.length);

    // Select everything, then narrow to pending
    await page.check('[data-testid="select-item-0"]');
    await page.click('[data-testid="select-all-visible"]');
    await expect(page.locator('[data-testid="selected-count"]')).toContainText(`${FIXTURE.length} items selected`);

    // Click select pending
    await page.click('[data-testid="select-pending"]');

    // Only pending items should be selected
    await expect(page.locator('[data-testid="selected-count"]')).toContainText(`${pendingIds.length} items selected`);
    const rows = page.locator('[data-testid="queue-item"]');
    for (let i = 0; i < FIXTURE.length; i++) {
      const isPending = (await rows.nth(i).locator('[data-testid="status-badge"]').textContent())?.trim() === 'pending';
      const checkbox = page.locator(`[data-testid="select-item-${i}"]`);
      if (isPending) {
        await expect(checkbox).toBeChecked();
      } else {
        await expect(checkbox).not.toBeChecked();
      }
    }

    // Verify button exists and is clickable
    await expect(page.locator('[data-testid="select-pending"]')).toBeVisible();
  });

  // BUILT: handleDeselectAll BulkApprovalActions.tsx:73-75 (button :139-145)
  test('should clear selection', async ({ page }) => {
    // First select some items
    await selectFirstThenAllVisible(page);

    // Then clear selection
    await page.click('[data-testid="clear-selection"]');

    // All items should be unchecked
    const checkboxes = page.locator('[data-testid^="select-item-"]');
    const count = await checkboxes.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const checkbox = checkboxes.nth(i);
      const isChecked = await checkbox.isChecked();
      expect(isChecked).toBe(false);
    }

    // Bulk actions bar should be hidden
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  // BUILT: "Approve (N)" opens the options panel (BulkApprovalActions.tsx:153-205); priority range :172-179
  test('should bulk approve with priority', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click approve (opens the approval options panel)
    await page.click('[data-testid="bulk-approve-button"]');

    // Should show approval options
    await expect(page.locator('[data-testid="approval-options-panel"]')).toBeVisible({ timeout: 5000 });

    // Change priority
    await page.fill('[data-testid="priority-input"]', '8');

    // Confirm bulk approve
    await page.click('[data-testid="confirm-bulk-approve"]');

    // Each pending item is approved with the chosen priority
    await expect.poll(() => mock.rpcCalls.length).toBe(pendingIds.length);
    expect(mock.rpcCalls.map((c) => c.fn)).toEqual(pendingIds.map(() => 'approve_ingestion'));
    expect(mock.rpcCalls.map((c) => c.body.p_id).sort()).toEqual([...pendingIds].sort());
    for (const call of mock.rpcCalls) expect(call.body.p_priority).toBe(8);

    // Selection should be cleared
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  // BUILT: default priority state 5 (BulkApprovalActions.tsx:55)
  test('should use default priority of 5', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Approve without touching the priority slider
    await page.click('[data-testid="bulk-approve-button"]');
    await page.click('[data-testid="confirm-bulk-approve"]');

    await expect.poll(() => mock.rpcCalls.length).toBe(pendingIds.length);
    for (const call of mock.rpcCalls) expect(call.body.p_priority).toBe(5);
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  test('should not approve non-pending items', async ({ page }) => {
    // This test checks that non-pending items are excluded from bulk approval

    // Show all items (including non-pending)
    await page.selectOption('[data-testid="queue-status-filter"]', 'all');
    const allItems = page.locator('[data-testid="queue-item"]');
    await expect(allItems).toHaveCount(FIXTURE.length);

    // Select all visible (the bar and its controls render once a row is selected)
    await page.check('[data-testid="select-item-0"]');
    await page.click('[data-testid="select-all-visible"]');
    await expect(page.locator('[data-testid="selected-count"]')).toContainText(`${FIXTURE.length} items selected`);

    // Approve button counts pending items only (BulkApprovalActions.tsx:59, :159)
    const approveButton = page.locator('[data-testid="bulk-approve-button"]');
    await expect(approveButton).toHaveText(`Approve (${pendingIds.length})`);

    // And approving sends only the pending ids
    await approveButton.click();
    await page.click('[data-testid="confirm-bulk-approve"]');
    await expect.poll(() => mock.rpcCalls.length).toBe(pendingIds.length);
    expect(mock.rpcCalls.map((c) => c.body.p_id).sort()).toEqual([...pendingIds].sort());
  });

  // BUILT: approve button disabled + "Processing..." while processing (BulkApprovalActions.tsx:156-159, page.tsx:229/242)
  test('should disable approve when processing', async ({ page }) => {
    mock.rpcDelayMs = 1500;

    // Select some items
    await selectFirstThenAllVisible(page);

    // Start bulk approve
    await page.click('[data-testid="bulk-approve-button"]');
    await page.click('[data-testid="confirm-bulk-approve"]');

    // Button should be disabled during processing
    await expect(page.locator('[data-testid="bulk-approve-button"]')).toBeDisabled();
    await expect(page.locator('[data-testid="bulk-approve-button"]')).toContainText('Processing...');

    // Wait for processing to complete: every pending item approved, selection cleared
    await expect.poll(() => mock.rpcCalls.length, { timeout: 10000 }).toBe(pendingIds.length);
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible({ timeout: 10000 });
  });

  // BUILT: reject panel BulkApprovalActions.tsx:209-284
  test('should bulk reject with reason', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Should show reject options
    await expect(page.locator('[data-testid="reject-options-panel"]')).toBeVisible({ timeout: 5000 });

    // Enter custom reason
    await page.fill('[data-testid="reject-reason"]', 'Low quality content');

    // Confirm reject
    await page.click('[data-testid="confirm-bulk-reject"]');

    // Each selected item is rejected with the reason; selection cleared
    await expect.poll(() => mock.rpcCalls.length).toBe(pendingIds.length);
    for (const call of mock.rpcCalls) {
      expect(call.fn).toBe('reject_ingestion');
      expect(call.body.p_reason).toBe('Low quality content');
    }
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  // BUILT: default reason 'Bulk rejected' (BulkApprovalActions.tsx:91)
  test('should use default rejection reason', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Confirm without entering reason
    await page.click('[data-testid="confirm-bulk-reject"]');

    await expect.poll(() => mock.rpcCalls.length).toBe(pendingIds.length);
    for (const call of mock.rpcCalls) {
      expect(call.fn).toBe('reject_ingestion');
      expect(call.body.p_reason).toBe('Bulk rejected');
    }
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  // BUILT: quick reasons BulkApprovalActions.tsx:241-260
  test('should pre-fill quick rejection reasons', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Should show quick reason buttons
    await expect(page.locator('[data-testid="quick-reason-duplicate"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-low-quality"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-irrelevant"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-nsfw"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-copyright"]')).toBeVisible();
  });

  // BUILT: setRejectionReason(reason) BulkApprovalActions.tsx:248
  test('should set reason when quick reason clicked', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Click quick reason
    await page.click('[data-testid="quick-reason-duplicate"]');

    // Reason textarea should be filled
    const reasonTextarea = page.locator('[data-testid="reject-reason"]');
    await expect(reasonTextarea).toHaveValue('Duplicate');
  });

  // BUILT: "{n} / 500" counter BulkApprovalActions.tsx:236-238
  test('should show character count for rejection reason', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Enter custom reason
    await page.fill('[data-testid="reject-reason"]', 'Test reason');

    // Should show character count
    await expect(page.locator('[data-testid="reason-char-count"]')).toContainText('11');
  });

  // BUILT: maxLength={500} BulkApprovalActions.tsx:234
  test('should enforce max length of 500 for rejection reason', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Try to enter very long reason
    const _longReason = 'a'.repeat(1000);
    await page.fill('[data-testid="reject-reason"]', _longReason);

    // Should be truncated or have maxLength attribute
    const actualValue = await page.inputValue('[data-testid="reject-reason"]');
    expect(actualValue.length).toBeLessThanOrEqual(500);
  });

  // BUILT: Export CSV BulkApprovalActions.tsx:286-295 -> handleExport page.tsx:279-302
  test('should export selected to CSV', async ({ page }) => {
    // Select some items
    await selectFirstThenAllVisible(page);

    const exportButton = page.locator('[data-testid="export-csv-button"]');
    await expect(exportButton).toBeVisible();

    // Handle file download
    const downloadPromise = page.waitForEvent('download');

    // Click export
    await exportButton.click();

    // Wait for download
    const download = await downloadPromise;

    // Verify file was downloaded
    expect(download.suggestedFilename()).toContain('.csv');
  });

  // BUILT: inline panel behind toggle, page.tsx:351-361 -> :379-387
  test('should open approval rules config', async ({ page }) => {
    // Click approval rules button
    await page.click('[data-testid="approval-rules-button"]');

    // Should show approval rules panel
    await expect(page.locator('[data-testid="approval-rules-panel"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="approval-rules-button"]')).toContainText('Hide Rules');
  });

  // BUILT: rules list ApprovalRulesConfig.tsx:306-370; Enable/Disable toggle :346-352
  test('should list all rules with enable/disable toggle', async ({ page }) => {
    // Rules are client state (page.tsx:71), so create one first
    await openNewRuleEditor(page);
    await page.fill('#rule-name', 'Toggle Me');
    await saveRuleAndExpectListed(page, 'Toggle Me');

    // Check for rules list
    await expect(page.locator('[data-testid="approval-rules-list"]')).toBeVisible();
    await expect(page.locator('[data-testid="approval-rule-item"]')).toHaveCount(1);

    // First rule should have enable toggle
    const toggle = page.locator('[data-testid="rule-toggle-0"]');
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveText('Disable');
    await toggle.click();
    await expect(toggle).toHaveText('Enable');
    await expect(page.locator('[data-testid="approval-rule-item"]').first()).toContainText('Disabled');
  });

  // BUILT: "+ New Rule" ApprovalRulesConfig.tsx:294-301 -> modal :383-608
  test('should open create rule modal', async ({ page }) => {
    await openRulesPanel(page);

    // Click new rule button
    await page.click('[data-testid="new-rule-button"]');

    // Should show create/edit rule modal
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });
  });

  // BUILT: save disabled while name is blank, ApprovalRulesConfig.tsx:600
  test('should validate rule name is required', async ({ page }) => {
    await openNewRuleEditor(page);

    // Cannot save without a name
    await expect(page.locator('[data-testid="save-rule"]')).toBeDisabled();

    // Whitespace-only is still rejected
    await page.fill('#rule-name', '   ');
    await expect(page.locator('[data-testid="save-rule"]')).toBeDisabled();

    // A real name enables save
    await page.fill('#rule-name', 'Named Rule');
    await expect(page.locator('[data-testid="save-rule"]')).toBeEnabled();
  });

  // BUILT: condition inputs ApprovalRulesConfig.tsx:459-526; priority range :551-570 (auto-approve only)
  test('should create rule with conditions', async ({ page }) => {
    await openNewRuleEditor(page);

    // Enter rule name
    await page.fill('#rule-name', 'Auto-approve TED');

    // Select source type condition
    await page.selectOption('#source-type', 'youtube');

    // Enter channel condition
    await page.fill('#channel-contains', 'TED');

    // Priority is shown for auto-approve rules
    await page.locator('[data-testid="rule-editor-modal"]').getByRole('button', { name: 'Auto-Approve', exact: true }).click();
    await page.fill('#rule-priority', '8');

    // Click save
    const item = await saveRuleAndExpectListed(page, 'Auto-approve TED');
    await expect(item.locator('[data-testid="rule-condition-summary"]')).toHaveText('When: YouTube, channel contains "TED"');
    await expect(item).toContainText('Priority: 8');
  });

  // BUILT: Edit ApprovalRulesConfig.tsx:353-359 -> openEditModal :158-170, update :177-184
  test('should edit existing rule', async ({ page }) => {
    await openNewRuleEditor(page);
    await page.fill('#rule-name', 'Original Rule');
    await saveRuleAndExpectListed(page, 'Original Rule');

    // Click edit button on first rule
    await page.click('[data-testid="edit-rule-0"]');

    // Should show rule editor with existing data
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#rule-name')).toHaveValue('Original Rule');

    // Modify rule name
    await page.fill('#rule-name', 'Updated Rule Name');

    // Save
    await saveRuleAndExpectListed(page, 'Updated Rule Name');
    await expect(page.locator('[data-testid="approval-rule-item"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="approval-rule-item"]').filter({ hasText: 'Original Rule' })).toHaveCount(0);
  });

  // BUILT: Delete -> ConfirmDialog ApprovalRulesConfig.tsx:360-366, :681-690
  test('should delete rule after confirmation', async ({ page }) => {
    await openNewRuleEditor(page);
    await page.fill('#rule-name', 'Doomed Rule');
    await saveRuleAndExpectListed(page, 'Doomed Rule');

    // Click delete button on first rule
    await page.click('[data-testid="delete-rule-0"]');

    // Should show confirmation dialog
    const dialog = page.getByRole('dialog', { name: 'Delete Rule' });
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="approval-rule-item"]')).toHaveCount(1);

    // Confirm delete
    await dialog.getByRole('button', { name: 'Delete', exact: true }).click();

    // Rule is removed
    await expect(dialog).not.toBeVisible();
    await expect(page.locator('[data-testid="approval-rule-item"]')).toHaveCount(0);
  });

  // BUILT: formatConditionSummary ApprovalRulesConfig.tsx:248-268, rendered :328-330
  test('should format condition summary correctly', async ({ page }) => {
    await openNewRuleEditor(page);
    await page.fill('#rule-name', 'Summary Rule');
    await page.selectOption('#source-type', 'youtube');
    await page.fill('#title-contains', 'tutorial');
    await page.fill('#min-duration', '60');
    const item = await saveRuleAndExpectListed(page, 'Summary Rule');

    const summary = item.locator('[data-testid="rule-condition-summary"]');
    await expect(summary).toBeVisible();
    await expect(summary).toHaveText('When: YouTube, title contains "tutorial", duration ≥ 60s');

    // A rule without conditions reads "Always match"
    await page.click('[data-testid="new-rule-button"]');
    await page.fill('#rule-name', 'Catch All');
    const catchAll = await saveRuleAndExpectListed(page, 'Catch All');
    await expect(catchAll.locator('[data-testid="rule-condition-summary"]')).toHaveText('When: Always match');
  });

  // fixme: UI unwired: rule-test action not rendered (page.tsx:380-386 passes no onTestRule; button gated at ApprovalRulesConfig.tsx:529)
  test.fixme('should test rule against pending items', async ({ page }) => {
    await openNewRuleEditor(page);
    await page.fill('#rule-name', 'Testable Rule');
    await saveRuleAndExpectListed(page, 'Testable Rule');

    // Click test rule button
    await page.click('[data-testid="test-rule-0"]');

    // Should show test results
    await expect(page.locator('[data-testid="rule-test-results"]')).toBeVisible({ timeout: 5000 });
  });

  // fixme: UI unwired: execution log not rendered (page.tsx:380-386 passes no onFetchLog; "View Log" gated at ApprovalRulesConfig.tsx:284)
  test.fixme('should show execution log modal', async ({ page }) => {
    await openRulesPanel(page);

    // Open the execution log
    await page.click('[data-testid="view-execution-log"]');

    // Should show execution log modal
    await expect(page.locator('[data-testid="execution-log-modal"]')).toBeVisible({ timeout: 5000 });
  });

  // BUILT: source type select ApprovalRulesConfig.tsx:461-471
  // renamed-from: should match by source type condition
  // (asserts the saved rule's condition summary; the UI shows no per-item match preview)
  test('should save a rule with a source type condition', async ({ page }) => {
    await openNewRuleEditor(page);

    // Enter rule name
    await page.fill('#rule-name', 'YouTube Filter');

    // Select source type
    await page.selectOption('#source-type', 'youtube');

    // Save
    const item = await saveRuleAndExpectListed(page, 'YouTube Filter');
    await expect(item.locator('[data-testid="rule-condition-summary"]')).toHaveText('When: YouTube');
  });

  // BUILT: channel input ApprovalRulesConfig.tsx:476-484
  // renamed-from: should match by channel contains condition
  // (asserts the saved rule's condition summary; the UI shows no per-item match preview)
  test('should save a rule with a channel contains condition', async ({ page }) => {
    await openNewRuleEditor(page);

    // Enter rule name
    await page.fill('#rule-name', 'Channel Filter');

    // Enter channel
    await page.fill('#channel-contains', 'TED');

    // Save
    const item = await saveRuleAndExpectListed(page, 'Channel Filter');
    await expect(item.locator('[data-testid="rule-condition-summary"]')).toHaveText('When: channel contains "TED"');
  });

  // BUILT: title input ApprovalRulesConfig.tsx:489-497
  // renamed-from: should match by title contains condition
  // (asserts the saved rule's condition summary; the UI shows no per-item match preview)
  test('should save a rule with a title contains condition', async ({ page }) => {
    await openNewRuleEditor(page);

    // Enter rule name
    await page.fill('#rule-name', 'Title Filter');

    // Enter title keyword
    await page.fill('#title-contains', 'tutorial');

    // Save
    const item = await saveRuleAndExpectListed(page, 'Title Filter');
    await expect(item.locator('[data-testid="rule-condition-summary"]')).toHaveText('When: title contains "tutorial"');
  });

  // BUILT: duration inputs ApprovalRulesConfig.tsx:501-526
  // renamed-from: should match by duration range condition
  // (asserts the saved rule's condition summary; the UI shows no per-item match preview)
  test('should save a rule with a duration range condition', async ({ page }) => {
    await openNewRuleEditor(page);

    // Enter rule name
    await page.fill('#rule-name', 'Duration Filter');

    // Set duration range
    await page.fill('#min-duration', '300'); // 5 minutes
    await page.fill('#max-duration', '3600'); // 1 hour

    // Save
    const item = await saveRuleAndExpectListed(page, 'Duration Filter');
    await expect(item.locator('[data-testid="rule-condition-summary"]')).toHaveText('When: duration ≥ 300s, duration ≤ 3600s');
  });

  // BUILT: action buttons ApprovalRulesConfig.tsx:434-451; priority :551-570; listed :338-340
  test('should set priority for auto-approve rules', async ({ page }) => {
    await openNewRuleEditor(page);

    // Enter rule name
    await page.fill('#rule-name', 'High Priority Auto-approve');

    // Priority control is only offered for auto-approve
    await expect(page.locator('#rule-priority')).toHaveCount(0);

    // Set action to auto-approve
    await page.locator('[data-testid="rule-editor-modal"]').getByRole('button', { name: 'Auto-Approve', exact: true }).click();

    // Set priority
    await page.fill('#rule-priority', '9');

    // Save
    const item = await saveRuleAndExpectListed(page, 'High Priority Auto-approve');
    await expect(item).toContainText('Auto-Approve');
    await expect(item).toContainText('Priority: 9');
  });

  // fixme: behaviour mismatch: no Escape handling. The rules panel is inline (page.tsx:379-387), and the rule editor closes only via overlay click or Cancel (ApprovalRulesConfig.tsx:384, :589-595); no keydown handler exists
  test.fixme('should close modals on escape key', async ({ page }) => {
    await openNewRuleEditor(page);

    // Press escape
    await page.keyboard.press('Escape');

    // Modal should close
    await expect(page.locator('[data-testid="rule-editor-modal"]')).not.toBeVisible();
  });

  // BUILT: overlay onClick={handleCloseModal} ApprovalRulesConfig.tsx:384 (dialog stops propagation :387)
  test('should close modals on overlay click', async ({ page }) => {
    await openNewRuleEditor(page);

    // Clicking inside the dialog does not close it
    await page.locator('#rule-name').click();
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible();

    // Click overlay (a corner, outside the centred dialog)
    await page.locator('[data-testid="modal-overlay"]').click({ position: { x: 5, y: 5 } });

    // Modal should close
    await expect(page.locator('[data-testid="rule-editor-modal"]')).not.toBeVisible();
  });

  // BUILT: "(N can be approved)" BulkApprovalActions.tsx:116-120
  test('should show pending count when some selected are pending', async ({ page }) => {
    // Mixed statuses are only visible under "All"
    await page.selectOption('[data-testid="queue-status-filter"]', 'all');
    await expect(page.locator('[data-testid="queue-item"]')).toHaveCount(FIXTURE.length);

    // Select items
    await page.check('[data-testid="select-item-0"]');
    await page.click('[data-testid="select-all-visible"]');

    // Check for pending count message
    const pendingCount = page.locator('[data-testid="pending-count-message"]');
    await expect(pendingCount).toBeVisible();
    await expect(pendingCount).toContainText(`(${pendingIds.length} can be approved)`);
  });

  test('should display singular "item" when one selected', async ({ page }) => {
    const queueItems = page.locator('[data-testid="queue-item"]');
    await expect(queueItems).toHaveCount(pendingIds.length);

    // Select just one item
    await page.check('[data-testid="select-item-0"]');

    // Should say "1 item selected" not "1 items selected"
    await expect(page.locator('[data-testid="selected-count"]')).toContainText('1 item selected');
    await expect(page.locator('[data-testid="selected-count"]')).not.toContainText('1 items');
  });

  // BUILT: status select page.tsx:414-426 drives fetchIngestionQueue status filter (:92-96)
  test('should filter queue by status', async ({ page }) => {
    // Narrow to a different status first
    await page.selectOption('[data-testid="queue-status-filter"]', 'approved');
    await expect(page.locator('[data-testid="queue-item"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="status-badge"]').first()).toHaveText('approved');

    // Select status filter
    await page.selectOption('[data-testid="queue-status-filter"]', 'pending');

    // Wait for filter to apply by waiting for table to update
    await page.waitForSelector('[data-testid="ingestion-queue-table"]', { state: 'visible' });
    await expect(page.locator('[data-testid="queue-item"]')).toHaveCount(pendingIds.length);

    // Queue table should still be visible
    await expect(page.locator('[data-testid="ingestion-queue-table"]')).toBeVisible();
    expect(mock.queueRequests.some((q) => q.includes('status=eq.approved'))).toBe(true);
  });
});
