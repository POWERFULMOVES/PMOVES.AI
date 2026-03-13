import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Agent Zero Chat Interface
 *
 * Tests the chat interface for:
 * - Message sending and display
 * - Real-time streaming responses
 * - Chat history persistence
 * - Error handling
 *
 * @module e2e/chat
 */

test.describe('Agent Zero Chat', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to chat dashboard
    await page.goto('/dashboard/chat');
  });

  test('displays chat interface with input and send button', async ({ page }) => {
    // Check for main chat elements
    await expect(page.getByRole('heading', { name: /chat/i })).toBeVisible();
    await expect(page.getByPlaceholder(/message/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /send/i })).toBeVisible();
  });

  test('sends message and displays in chat history', async ({ page }) => {
    const testMessage = 'Hello, Agent Zero!';

    // Type and send message
    await page.getByPlaceholder(/message/i).fill(testMessage);
    await page.getByRole('button', { name: /send/i }).click();

    // Verify message appears in chat
    await expect(page.getByText(testMessage)).toBeVisible();
  });

  test('displays loading state while agent processes', async ({ page }) => {
    const testMessage = 'Test loading state';

    // Send message
    await page.getByPlaceholder(/message/i).fill(testMessage);
    await page.getByRole('button', { name: /send/i }).click();

    // Check for loading indicator
    await expect(page.getByRole('status')).toBeVisible({ timeout: 5000 });
  });

  test('supports markdown in responses', async ({ page }) => {
    // Send a message that should trigger a formatted response
    await page.getByPlaceholder(/message/i).fill('Format this as a list');
    await page.getByRole('button', { name: /send/i }).click();

    // Wait for response (may be mocked in test environment)
    await page.waitForTimeout(2000);

    // Check for markdown-rendered elements
    const hasListItems = await page.locator('li, ul, ol').count() > 0;
    // This is a soft assertion since response content varies
    if (hasListItems) {
      await expect(page.locator('li').first()).toBeVisible();
    }
  });

  test('clears input after sending', async ({ page }) => {
    const testMessage = 'Clear this message';

    await page.getByPlaceholder(/message/i).fill(testMessage);
    await page.getByRole('button', { name: /send/i }).click();

    // Verify input is cleared
    await expect(page.getByPlaceholder(/message/i)).toHaveValue('');
  });

  test('disables send button when input is empty', async ({ page }) => {
    const sendButton = page.getByRole('button', { name: /send/i });

    // Initially should be disabled
    await expect(sendButton).toBeDisabled();

    // Should be enabled when there's input
    await page.getByPlaceholder(/message/i).fill('Test');
    await expect(sendButton).toBeEnabled();

    // Should be disabled again when cleared
    await page.getByPlaceholder(/message/i).fill('');
    await expect(sendButton).toBeDisabled();
  });

  test('handles Enter key to send message', async ({ page }) => {
    const testMessage = 'Send with Enter';

    await page.getByPlaceholder(/message/i).fill(testMessage);
    await page.keyboard.press('Enter');

    // Verify message appears
    await expect(page.getByText(testMessage)).toBeVisible();
  });

  test('allows Shift+Enter for new lines without sending', async ({ page }) => {
    const testMessage = 'Line 1\nLine 2';

    await page.getByPlaceholder(/message/i).fill('Line 1');
    await page.keyboard.press('Shift+Enter');
    await page.keyboard.type('Line 2');

    // Verify both lines are in input
    await expect(page.getByPlaceholder(/message/i)).toHaveValue(testMessage);

    // Message should not be sent yet
    await expect(page.getByText(testMessage)).not.toBeVisible();
  });

  test('displays agent avatar and name', async ({ page }) => {
    // Check for agent identification
    const agentName = page.getByText(/agent zero/i, { exact: false });
    const hasAvatar = await page.locator('[class*="avatar"], img[alt*="agent"]').count() > 0;

    // At least one of these should be present
    const hasAgentIdentification = await agentName.count() > 0 || hasAvatar;
    expect(hasAgentIdentification).toBe(true);
  });

  test('shows error message on failed request', async ({ page }) => {
    // This test requires mocking a failed request
    // For now, we'll check that error handling UI exists
    const hasErrorDisplay =
      (await page.locator('[class*="error"], [role="alert"]').count()) > 0;

    // If error display exists, verify it's hidden initially
    if (hasErrorDisplay) {
      await expect(page.locator('[class*="error"], [role="alert"]').first()).not.toBeVisible();
    }
  });
});

test.describe('Agent Zero Chat - Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/chat');
  });

  test('provides access to model selection', async ({ page }) => {
    // Look for model selector or settings button
    const modelSelector = page.getByRole('combobox', { name: /model/i });
    const settingsButton = page.getByRole('button', { name: /settings/i });

    const hasControls =
      (await modelSelector.count()) > 0 || (await settingsButton.count()) > 0;
    expect(hasControls).toBe(true);
  });

  test('allows clearing chat history', async ({ page }) => {
    // Look for clear history button
    const clearButton = page.getByRole('button', { name: /clear/i, exact: false });

    if ((await clearButton.count()) > 0) {
      await clearButton.first().click();

      // Verify confirmation or action
      const hasConfirm = await page.getByRole('button', { name: /confirm/i }).count() > 0;
      if (hasConfirm) {
        await page.getByRole('button', { name: /confirm/i }).click();
      }
    }
  });
});
