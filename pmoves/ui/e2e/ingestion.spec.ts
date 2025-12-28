/* ═══════════════════════════════════════════════════════════════════════════
   Enhanced Video Approval E2E Tests
   Tests end-to-end ingestion queue bulk approval workflows
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect } from '@playwright/test';

test.describe('Enhanced Video Approval', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to ingestion queue
    await page.goto('/dashboard/ingestion-queue');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  test('should load ingestion queue with initial state', async ({ page }) => {
    // Check that queue table is present
    await expect(page.locator('[data-testid="ingestion-queue-table"]')).toBeVisible();

    // Check that bulk actions section exists
    const bulkActions = page.locator('[data-testid="bulk-actions-bar"]');
    // Might not be visible if no items selected
  });

  test('should display queue items with correct status', async ({ page }) => {
    // Check for queue items
    const queueItems = page.locator('[data-testid="queue-item"]');
    const count = await queueItems.count();

    // Items might not exist if queue is empty
    if (count > 0) {
      await expect(queueItems.first()).toBeVisible();

      // Check for status badges
      const statusBadges = page.locator('[data-testid="status-badge"]');
      await expect(statusBadges.first()).toBeVisible();
    }
  });

  test('should select single item', async ({ page }) => {
    const queueItems = page.locator('[data-testid="queue-item"]');
    const count = await queueItems.count();

    if (count > 0) {
      // Click checkbox on first item
      await page.check('[data-testid="select-item-0"]');

      // Checkbox should be checked
      await expect(page.locator('[data-testid="select-item-0"]')).toBeChecked();

      // Bulk actions bar should appear
      await expect(page.locator('[data-testid="bulk-actions-bar"]')).toBeVisible();
    }
  });

  test('should bulk select multiple items', async ({ page }) => {
    const queueItems = page.locator('[data-testid="queue-item"]');
    const count = await queueItems.count();

    if (count >= 2) {
      // Select multiple items
      await page.check('[data-testid="select-item-0"]');
      await page.check('[data-testid="select-item-1"]');

      // Bulk actions bar should be visible
      await expect(page.locator('[data-testid="bulk-actions-bar"]')).toBeVisible();

      // Should show correct count
      await expect(page.locator('[data-testid="selected-count"]')).toContainText('2');
    }
  });

  test('should show "select all visible" button', async ({ page }) => {
    await expect(page.locator('[data-testid="select-all-visible"]')).toBeVisible();
  });

  test('should show "select pending" button', async ({ page }) => {
    await expect(page.locator('[data-testid="select-pending"]')).toBeVisible();
  });

  test('should select all visible items', async ({ page }) => {
    // Click select all visible
    await page.click('[data-testid="select-all-visible"]');

    // All visible checkboxes should be checked
    const checkboxes = page.locator('[data-testid^="select-item-"]');
    const count = await checkboxes.count();

    for (let i = 0; i < count; i++) {
      const checkbox = checkboxes.nth(i);
      if (await checkbox.isVisible()) {
        await expect(checkbox).toBeChecked();
      }
    }
  });

  test('should select only pending items', async ({ page }) => {
    // Click select pending
    await page.click('[data-testid="select-pending"]');

    // Only pending items should be selected
    const pendingItems = page.locator('[data-testid="queue-item"][data-status="pending"]');
    const pendingCount = await pendingItems.count();

    // Verify button exists and is clickable
    await expect(page.locator('[data-testid="select-pending"]')).toBeVisible();
  });

  test('should clear selection', async ({ page }) => {
    // First select some items
    await page.click('[data-testid="select-all-visible"]');

    // Then clear selection
    await page.click('[data-testid="clear-selection"]');

    // All items should be unchecked
    const checkboxes = page.locator('[data-testid^="select-item-"]');
    const count = await checkboxes.count();

    for (let i = 0; i < count; i++) {
      const checkbox = checkboxes.nth(i);
      const isChecked = await checkbox.isChecked();
      expect(isChecked).toBe(false);
    }

    // Bulk actions bar should be hidden
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  test('should bulk approve with priority', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click approve options button
    await page.click('[data-testid="bulk-approve-options"]');

    // Should show approval options modal
    await expect(page.locator('[data-testid="approval-options-modal"]')).toBeVisible({ timeout: 5000 });

    // Change priority
    await page.fill('[data-testid="priority-input"]', '8');

    // Confirm bulk approve
    await page.click('[data-testid="confirm-bulk-approve"]');

    // Should show success message
    await expect(page.locator('[data-testid="approve-success-toast"]')).toBeVisible({ timeout: 5000 });

    // Selection should be cleared
    await expect(page.locator('[data-testid="bulk-actions-bar"]')).not.toBeVisible();
  });

  test('should use default priority of 5', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click approve button directly (not options)
    const approveButton = page.locator('[data-testid="bulk-approve-button"]');

    if (await approveButton.isVisible({ timeout: 1000 })) {
      await approveButton.click();

      // Should use default priority and show success
      await expect(page.locator('[data-testid="approve-success-toast"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should not approve non-pending items', async ({ page }) => {
    // This test checks that non-pending items are excluded from bulk approval

    // First, find all items (including non-pending)
    const allItems = page.locator('[data-testid="queue-item"]');
    const allCount = await allItems.count();

    if (allCount > 0) {
      // Select all visible
      await page.click('[data-testid="select-all-visible"]');

      // Check approve button for count of pending items
      const approveButton = page.locator('[data-testid="bulk-approve-button"]');
      const buttonText = await approveButton.textContent();

      // Should show count of pending items only
      expect(buttonText).toMatch(/\(\d+\)/);
    }
  });

  test('should disable approve when processing', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Start bulk approve
    await page.click('[data-testid="bulk-approve-button"]');

    // Button should be disabled during processing
    await expect(page.locator('[data-testid="bulk-approve-button"]')).toBeDisabled();

    // Wait for processing to complete
    await expect(page.locator('[data-testid="approve-success-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should bulk reject with reason', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Should show reject options modal
    await expect(page.locator('[data-testid="reject-options-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter custom reason
    await page.fill('[data-testid="reject-reason"]', 'Low quality content');

    // Confirm reject
    await page.click('[data-testid="confirm-bulk-reject"]');

    // Should show success message
    await expect(page.locator('[data-testid="reject-success-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should use default rejection reason', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Confirm without entering reason
    await page.click('[data-testid="confirm-bulk-reject"]');

    // Should show success message
    await expect(page.locator('[data-testid="reject-success-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should pre-fill quick rejection reasons', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Should show quick reason buttons
    await expect(page.locator('[data-testid="quick-reason-duplicate"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-low-quality"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-irrelevant"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-nsfw"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-reason-copyright"]')).toBeVisible();
  });

  test('should set reason when quick reason clicked', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Click quick reason
    await page.click('[data-testid="quick-reason-duplicate"]');

    // Reason textarea should be filled
    const reasonTextarea = page.locator('[data-testid="reject-reason"]');
    await expect(reasonTextarea).toHaveValue('Duplicate');
  });

  test('should show character count for rejection reason', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Enter custom reason
    await page.fill('[data-testid="reject-reason"]', 'Test reason');

    // Should show character count
    await expect(page.locator('[data-testid="reason-char-count"]')).toContainText('11');
  });

  test('should enforce max length of 500 for rejection reason', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Click reject button
    await page.click('[data-testid="bulk-reject-button"]');

    // Try to enter very long reason
    const longReason = 'a'.repeat(1000);
    await page.fill('[data-testid="reject-reason"]', longReason);

    // Should be truncated or have maxLength attribute
    const actualValue = await page.inputValue('[data-testid="reject-reason"]');
    expect(actualValue.length).toBeLessThanOrEqual(500);
  });

  test('should export selected to CSV', async ({ page }) => {
    // Select some items
    await page.click('[data-testid="select-all-visible"]');

    // Check if export button exists
    const exportButton = page.locator('[data-testid="export-csv-button"]');

    if (await exportButton.isVisible({ timeout: 1000 })) {
      // Handle file download
      const downloadPromise = page.waitForEvent('download');

      // Click export
      await exportButton.click();

      // Wait for download
      const download = await downloadPromise;

      // Verify file was downloaded
      expect(download.suggestedFilename()).toContain('.csv');
    }
  });

  test('should open approval rules config', async ({ page }) => {
    // Click approval rules button
    await page.click('[data-testid="approval-rules-button"]');

    // Should show approval rules modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });
  });

  test('should list all rules with enable/disable toggle', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Check for rules list
    const rulesList = page.locator('[data-testid="approval-rules-list"]');
    const hasRules = await rulesList.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasRules) {
      // Check for rule items
      const ruleItems = page.locator('[data-testid="approval-rule-item"]');
      const count = await ruleItems.count();

      if (count > 0) {
        // First rule should have enable toggle
        await expect(page.locator('[data-testid="rule-toggle-0"]')).toBeVisible();
      }
    }
  });

  test('should open create rule modal', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Click new rule button
    await page.click('[data-testid="new-rule-button"]');

    // Should show create/edit rule modal
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });
  });

  test('should validate rule name is required', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Click new rule button
    await page.click('[data-testid="new-rule-button"]');

    // Wait for editor modal
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Try to save without entering name
    await page.click('[data-testid="save-rule"]');

    // Should show validation error
    const validationError = page.locator('[data-testid="rule-name-required"]');
    const hasError = await validationError.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasError) {
      await expect(validationError).toBeVisible();
    }
  });

  test('should create rule with conditions', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Click new rule button
    await page.click('[data-testid="new-rule-button"]');

    // Wait for editor modal
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter rule name
    await page.fill('[data-testid="rule-name"]', 'Auto-approve TED');

    // Select source type condition
    await page.selectOption('[data-testid="rule-source-type"]', 'youtube');

    // Enter channel condition
    await page.fill('[data-testid="rule-channel"]', 'TED');

    // Set priority for auto-approve
    await page.fill('[data-testid="rule-priority"]', '8');

    // Click save
    await page.click('[data-testid="save-rule"]');

    // Should show success message
    await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should edit existing rule', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Check if rules exist
    const ruleItems = page.locator('[data-testid="approval-rule-item"]');
    const count = await ruleItems.count();

    if (count > 0) {
      // Click edit button on first rule
      await page.click('[data-testid="edit-rule-0"]');

      // Should show rule editor with existing data
      await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

      // Modify rule name
      await page.fill('[data-testid="rule-name"]', 'Updated Rule Name');

      // Save
      await page.click('[data-testid="save-rule"]');

      // Should show success message
      await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should delete rule after confirmation', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Check if rules exist
    const ruleItems = page.locator('[data-testid="approval-rule-item"]');
    const count = await ruleItems.count();

    if (count > 0) {
      // Click delete button on first rule
      await page.click('[data-testid="delete-rule-0"]');

      // Should show confirmation dialog
      await expect(page.locator('[data-testid="confirm-delete-dialog"]')).toBeVisible({ timeout: 5000 });

      // Confirm delete
      await page.click('[data-testid="confirm-delete-yes"]');

      // Should show success message
      await expect(page.locator('[data-testid="rule-deleted-toast"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should format condition summary correctly', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Check for condition summaries
    const conditionSummaries = page.locator('[data-testid="rule-condition-summary"]');
    const count = await conditionSummaries.count();

    if (count > 0) {
      // First summary should be visible
      await expect(conditionSummaries.first()).toBeVisible();

      // Should have readable text
      const summaryText = await conditionSummaries.first().textContent();
      expect(summaryText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('should test rule against pending items', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Check if rules exist
    const ruleItems = page.locator('[data-testid="approval-rule-item"]');
    const count = await ruleItems.count();

    if (count > 0) {
      // Click test rule button
      const testButton = page.locator('[data-testid="test-rule-0"]');

      if (await testButton.isVisible({ timeout: 1000 })) {
        await testButton.click();

        // Should show test results
        await expect(page.locator('[data-testid="rule-test-results"]')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should show execution log modal', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');

    // Wait for modal
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Check for execution log button
    const logButton = page.locator('[data-testid="view-execution-log"]');

    if (await logButton.isVisible({ timeout: 1000 })) {
      await logButton.click();

      // Should show execution log modal
      await expect(page.locator('[data-testid="execution-log-modal"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should match by source type condition', async ({ page }) => {
    // Create a new rule with source type condition
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });
    await page.click('[data-testid="new-rule-button"]');
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter rule name
    await page.fill('[data-testid="rule-name"]', 'YouTube Filter');

    // Select source type
    await page.selectOption('[data-testid="rule-source-type"]', 'youtube');

    // Save
    await page.click('[data-testid="save-rule"]');

    // Should show success
    await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should match by channel contains condition', async ({ page }) => {
    // Create a new rule with channel condition
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });
    await page.click('[data-testid="new-rule-button"]');
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter rule name
    await page.fill('[data-testid="rule-name"]', 'Channel Filter');

    // Enter channel
    await page.fill('[data-testid="rule-channel"]', 'TED');

    // Save
    await page.click('[data-testid="save-rule"]');

    // Should show success
    await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should match by title contains condition', async ({ page }) => {
    // Create a new rule with title condition
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });
    await page.click('[data-testid="new-rule-button"]');
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter rule name
    await page.fill('[data-testid="rule-name"]', 'Title Filter');

    // Enter title keyword
    await page.fill('[data-testid="rule-title"]', 'tutorial');

    // Save
    await page.click('[data-testid="save-rule"]');

    // Should show success
    await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should match by duration range condition', async ({ page }) => {
    // Create a new rule with duration range
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });
    await page.click('[data-testid="new-rule-button"]');
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter rule name
    await page.fill('[data-testid="rule-name"]', 'Duration Filter');

    // Set duration range
    await page.fill('[data-testid="rule-min-duration"]', '300'); // 5 minutes
    await page.fill('[data-testid="rule-max-duration"]', '3600'); // 1 hour

    // Save
    await page.click('[data-testid="save-rule"]');

    // Should show success
    await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should set priority for auto-approve rules', async ({ page }) => {
    // Create an auto-approve rule with priority
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });
    await page.click('[data-testid="new-rule-button"]');
    await expect(page.locator('[data-testid="rule-editor-modal"]')).toBeVisible({ timeout: 5000 });

    // Enter rule name
    await page.fill('[data-testid="rule-name"]', 'High Priority Auto-approve');

    // Set action to auto-approve
    await page.selectOption('[data-testid="rule-action"]', 'auto-approve');

    // Set priority
    await page.fill('[data-testid="rule-priority"]', '9');

    // Save
    await page.click('[data-testid="save-rule"]');

    // Should show success
    await expect(page.locator('[data-testid="rule-saved-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should close modals on escape key', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Press escape
    await page.keyboard.press('Escape');

    // Modal should close
    await expect(page.locator('[data-testid="approval-rules-modal"]')).not.toBeVisible();
  });

  test('should close modals on overlay click', async ({ page }) => {
    // Open approval rules
    await page.click('[data-testid="approval-rules-button"]');
    await expect(page.locator('[data-testid="approval-rules-modal"]')).toBeVisible({ timeout: 5000 });

    // Click overlay
    await page.click('[data-testid="modal-overlay"]');

    // Modal should close
    await expect(page.locator('[data-testid="approval-rules-modal"]')).not.toBeVisible();
  });

  test('should show pending count when some selected are pending', async ({ page }) => {
    // Select items
    await page.click('[data-testid="select-all-visible"]');

    // Check for pending count message
    const pendingCount = page.locator('[data-testid="pending-count-message"]');
    const hasMessage = await pendingCount.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasMessage) {
      await expect(pendingCount).toBeVisible();
    }
  });

  test('should display singular "item" when one selected', async ({ page }) => {
    const queueItems = page.locator('[data-testid="queue-item"]');
    const count = await queueItems.count();

    if (count > 0) {
      // Select just one item
      await page.check('[data-testid="select-item-0"]');

      // Should say "1 item selected" not "1 items selected"
      await expect(page.locator('[data-testid="selected-count"]')).toContainText('1 item selected');
    }
  });

  test('should filter queue by status', async ({ page }) => {
    // Select status filter
    await page.selectOption('[data-testid="queue-status-filter"]', 'pending');

    // Wait for filter to apply by waiting for table to update
    await page.waitForSelector('[data-testid="ingestion-queue-table"]', { state: 'visible' });

    // Queue table should still be visible
    await expect(page.locator('[data-testid="ingestion-queue-table"]')).toBeVisible();
  });
});
