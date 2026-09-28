import { test, expect, type Page } from '@playwright/test';

/**
 * Backend-free mock for the two routes the chat page uses: GET /api/chat/messages
 * and POST /api/chat/send. Sent messages are echoed back by the next messages fetch,
 * which is what the page does after a successful send. `sendDelayMs` keeps the
 * "Sending..." state observable.
 */
async function mockChatBackend(page: Page, sendDelayMs = 0) {
  const items: Array<Record<string, unknown>> = [];
  await page.route('**/api/chat/messages*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items }) })
  );
  await page.route('**/api/chat/send', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    items.push({
      id: items.length + 1,
      owner_id: 'e2e-owner',
      role: 'user',
      agent: null,
      agent_id: null,
      avatar_url: null,
      content: body.content,
      message_type: 'text',
      session_id: null,
      metadata: null,
      created_at: new Date().toISOString(),
    });
    if (sendDelayMs) await new Promise((r) => setTimeout(r, sendDelayMs));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
}

/** An agent-authored message whose content is a two-item markdown list. */
function agentMarkdownReply() {
  return {
    id: 101,
    owner_id: 'e2e-owner',
    role: 'agent',
    agent: 'Agent Zero',
    agent_id: 'agent-zero',
    avatar_url: null,
    content: '- first item\n- second item',
    message_type: 'text',
    session_id: null,
    metadata: null,
    created_at: new Date().toISOString(),
  };
}

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
    // Chat send/list go through /api/chat/*, which needs Supabase; mock them so the suite runs without a backend.
    await mockChatBackend(page, 1500);
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

    // Loading state: the send button reads "Sending..." and is disabled while the request is in flight
    const sendButton = page.getByTestId('chat-send-button');
    await expect(sendButton).toHaveText(/sending/i, { timeout: 5000 });
    await expect(sendButton).toBeDisabled();
  });

  test('displays agent replies from the message feed verbatim', async ({ page }) => {
    // Serve an agent reply (routes registered later take precedence over the beforeEach mock)
    await page.route('**/api/chat/messages*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [agentMarkdownReply()] }),
      })
    );
    await page.reload();

    // Content renders in a whitespace-pre-wrap block (app/dashboard/chat/page.tsx), so the markdown
    // source, including its line break, reaches the page as-is under the agent's name.
    const reply = page.getByText('- first item', { exact: false });
    await expect(reply).toBeVisible();
    await expect(reply).toContainText('- second item');
    // The author label is the <span> above the content ({m.agent || m.role})
    await expect(page.locator('span').filter({ hasText: /^Agent Zero$/ })).toBeVisible();
  });

  // fixme: FEATURE NOT BUILT. The chat page renders message content as plain text
  // (<div className="text-sm whitespace-pre-wrap">{m.content}</div> in app/dashboard/chat/page.tsx);
  // there is no markdown renderer, so a markdown list reply never becomes list items. The old body
  // was vacuous (`if (count > 0)`), so it could never fail. No tracking issue yet.
  test.fixme('supports markdown in responses', async ({ page }) => {
    await page.route('**/api/chat/messages*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [agentMarkdownReply()] }),
      })
    );
    await page.reload();

    await expect(page.getByRole('listitem').filter({ hasText: 'first item' })).toBeVisible();
    await expect(page.getByRole('listitem').filter({ hasText: 'second item' })).toBeVisible();
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

  // Removed 2026-09-28 (lane test/e2e-reconcile-open-jev): 'allows Shift+Enter for new lines without sending'.
  // The message field is a single-line <input id="chatMessage"> and has never been a <textarea>
  // (git log --all -S'<textarea' -- app/dashboard/chat is empty), so multi-line entry is not a feature.
  test('displays agent avatar and name', async ({ page }) => {
    // Check for agent identification
    const agentName = page.getByText(/agent zero/i, { exact: false });
    const hasAvatar = await page.locator('[class*="avatar"], img[alt*="agent"]').count() > 0;

    // At least one of these should be present
    const hasAgentIdentification = await agentName.count() > 0 || hasAvatar;
    expect(hasAgentIdentification).toBe(true);
  });

  test('shows error message on failed request', async ({ page }) => {
    // Make the send fail (routes registered later take precedence over the beforeEach mock)
    await page.route('**/api/chat/send', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'e2e simulated failure' }) })
    );
    await page.getByPlaceholder(/message/i).fill('This send will fail');
    await page.getByTestId('chat-send-button').click();

    // The page surfaces the server's error in an alert and keeps the text for a retry
    await expect(page.getByRole('alert').filter({ hasText: 'e2e simulated failure' })).toBeVisible();
    await expect(page.getByPlaceholder(/message/i)).toHaveValue('This send will fail');
  });
});

test.describe('Agent Zero Chat - Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/chat');
  });

  test('provides access to agent selection', async ({ page }) => {
    // Current UI: a target-agent selector (not a model selector / settings button).
    const agentSelect = page.getByTestId('chat-agent-select');
    await expect(agentSelect).toBeVisible();
    await expect(agentSelect.locator('option')).toContainText(['Agent Zero', 'Archon']);
    await agentSelect.selectOption('archon');
    await expect(agentSelect).toHaveValue('archon');
  });

  // fixme: FEATURE NOT BUILT. app/dashboard/chat/page.tsx has no clear-history control (no
  // "clear" button, and /api/chat/* has no delete route the page calls). The old body was vacuous
  // (`if (count > 0)` with no assertion), so it could never fail. No tracking issue yet.
  // The body states the intended behaviour so it fails loudly once un-fixme'd against a real control.
  test.fixme('allows clearing chat history', async ({ page }) => {
    const clearButton = page.getByRole('button', { name: /clear/i });
    await expect(clearButton).toBeVisible();
    await clearButton.click();

    const confirm = page.getByRole('button', { name: /confirm/i });
    if (await confirm.isVisible()) await confirm.click();

    await expect(page.getByText(/no messages yet/i)).toBeVisible();
  });
});
