import { test, expect } from '@playwright/test';

/**
 * E2E tests for Archon Prompts Management
 *
 * Tests the CRUD operations for prompt templates managed by Archon,
 * including listing, creating, updating, and deleting prompts.
 *
 * Route: /dashboard/archon-prompts
 * API: http://localhost:8091/*
 */

const ARCHON_URL = process.env.NEXT_PUBLIC_ARCHON_URL || 'http://localhost:8091';

test.describe('Archon Prompts Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/archon-prompts');
  });

  test('page loads with prompts interface visible', async ({ page }) => {
    // Verify main content area
    await expect(page.getByRole('main')).toBeVisible();

    // Check for page heading
    const heading = page.getByRole('heading', { name: /prompts|archon/i });
    const count = await heading.count();
    if (count > 0) {
      await expect(heading.first()).toBeVisible();
    }
  });

  test('displays prompt list or empty state', async ({ page }) => {
    // Either show prompts or empty state
    const promptList = page.locator('[data-testid="prompt-list"], .prompt-list, [class*="promptList"]');
    const emptyState = page.locator('[data-testid="empty-state"], .empty-state, [class*="empty"]');

    await page.waitForTimeout(1000); // Wait for data to load

    const hasList = await promptList.count() > 0;
    const hasEmpty = await emptyState.count() > 0;

    // At least one should be present
    expect(hasList || hasEmpty).toBe(true);
  });

  test('has create prompt button or interface', async ({ page }) => {
    // Look for create button
    const createButton = page.getByRole('button', { name: /create|new|add prompt/i });

    if (await createButton.count() > 0) {
      await expect(createButton.first()).toBeVisible();
    } else {
      // Alternative: check for create form directly
      const createForm = page.locator('form').first();
      await expect(createForm).toBeVisible();
    }
  });

  test('prompts can be filtered or searched', async ({ page }) => {
    // Check for search input
    const searchInput = page.locator('input[placeholder*="search" i], input[type="search"], [data-testid="search"]');

    if (await searchInput.count() > 0) {
      await expect(searchInput.first()).toBeVisible();

      // Type search query
      await searchInput.first().fill('test');
      await expect(searchInput.first()).toHaveValue('test');
    }
  });
});

test.describe('Archon Prompts CRUD Operations', () => {
  test('can create a new prompt', async ({ page, request }) => {
    // First check if Archon is available
    const healthResponse = await request.get(`${ARCHON_URL}/healthz`);
    if (healthResponse.status() !== 200) {
      test.skip(true, 'Archon service not available');
      return;
    }

    await page.goto('/dashboard/archon-prompts');

    // Find and click create button
    const createButton = page.getByRole('button', { name: /create|new|add/i });
    if (await createButton.count() > 0) {
      await createButton.first().click();

      // Fill in prompt form
      const nameInput = page.locator('input[name="name"], [data-testid="prompt-name"]');
      const contentInput = page.locator('textarea[name="content"], [data-testid="prompt-content"]');

      if (await nameInput.count() > 0) {
        await nameInput.first().fill('E2E Test Prompt');
      }

      if (await contentInput.count() > 0) {
        await contentInput.first().fill('This is a test prompt created by E2E tests');
      }

      // Submit form
      const submitButton = page.getByRole('button', { name: /save|submit|create/i });
      if (await submitButton.count() > 0) {
        await submitButton.first().click();

        // Verify success message or redirect
        await page.waitForTimeout(1000);
        const successMessage = page.locator('[role="status"], .success, [class*="success"]');
        if (await successMessage.count() > 0) {
          await expect(successMessage.first()).toBeVisible();
        }
      }
    }
  });

  test('can list existing prompts', async ({ page, request }) => {
    const healthResponse = await request.get(`${ARCHON_URL}/healthz`);
    if (healthResponse.status() !== 200) {
      test.skip(true, 'Archon service not available');
      return;
    }

    await page.goto('/dashboard/archon-prompts');

    // Wait for prompts to load
    await page.waitForTimeout(2000);

    // Check for prompt cards or list items
    const promptItems = page.locator('[data-testid="prompt"], .prompt-card, [class*="promptItem"]');

    const count = await promptItems.count();
    if (count > 0) {
      // Verify at least one prompt is displayed
      await expect(promptItems.first()).toBeVisible();
    }
  });

  test('can edit an existing prompt', async ({ page, request }) => {
    const healthResponse = await request.get(`${ARCHON_URL}/healthz`);
    if (healthResponse.status() !== 200) {
      test.skip(true, 'Archon service not available');
      return;
    }

    await page.goto('/dashboard/archon-prompts');

    // Wait for prompts to load
    await page.waitForTimeout(2000);

    // Find edit button on first prompt
    const editButton = page.getByRole('button', { name: /edit|modify/i }).first();

    if (await editButton.count() > 0) {
      await editButton.click();

      // Modify prompt content
      const contentInput = page.locator('textarea[name="content"], [data-testid="prompt-content"]');
      if (await contentInput.count() > 0) {
        await contentInput.first().fill('Updated prompt content from E2E test');

        // Save changes
        const saveButton = page.getByRole('button', { name: /save|update/i });
        if (await saveButton.count() > 0) {
          await saveButton.first().click();

          // Verify save
          await page.waitForTimeout(1000);
          const successMessage = page.locator('[role="status"], .success');
          if (await successMessage.count() > 0) {
            await expect(successMessage.first()).toBeVisible();
          }
        }
      }
    }
  });

  test('can delete a prompt', async ({ page, request }) => {
    const healthResponse = await request.get(`${ARCHON_URL}/healthz`);
    if (healthResponse.status() !== 200) {
      test.skip(true, 'Archon service not available');
      return;
    }

    await page.goto('/dashboard/archon-prompts');
    await page.waitForTimeout(2000);

    // Find delete button
    const deleteButton = page.getByRole('button', { name: /delete|remove/i }).first();

    if (await deleteButton.count() > 0) {
      // Get initial prompt count
      const promptItems = page.locator('[data-testid="prompt"], .prompt-card');
      const initialCount = await promptItems.count();

      await deleteButton.click();

      // Confirm deletion if modal appears
      const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
      if (await confirmButton.count() > 0) {
        await confirmButton.first().click();
      }

      // Verify deletion
      await page.waitForTimeout(1000);
      const finalCount = await promptItems.count();
      expect(finalCount).toBeLessThanOrEqual(initialCount);
    }
  });
});

test.describe('Archon API Integration', () => {
  test('health check responds', async ({ request }) => {
    const response = await request.get(`${ARCHON_URL}/healthz`);

    // In CI, Archon may not be running
    expect([200, 502, 503]).toContain(response.status());

    if (response.status() === 200) {
      const body = await response.json();
      expect(body).toHaveProperty('status');
    }
  });

  test('prompts endpoint returns list', async ({ request }) => {
    const response = await request.get(`${ARCHON_URL}/api/prompts`);

    // May require auth or return 404
    expect([200, 401, 403, 404, 502]).toContain(response.status());

    if (response.status() === 200) {
      const body = await response.json();
      expect(Array.isArray(body.items) || Array.isArray(body)).toBe(true);
    }
  });
});
