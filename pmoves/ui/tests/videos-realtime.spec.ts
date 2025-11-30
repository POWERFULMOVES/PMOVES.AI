import { test, expect } from '@playwright/test';

// Helper: insert a dummy video row via Supabase REST using env
async function insertSmokeRow() {
  const rest = process.env.SUPABASE_REST_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!rest || !key) throw new Error('SUPABASE_REST_URL and SUPABASE_SERVICE_ROLE_KEY are required');

  const vid = `ui-smoke-${Date.now()}-${Math.floor(Math.random()*10000)}`;
  const body = {
    video_id: vid,
    namespace: 'pmoves',
    title: `UI Realtime Smoke: ${vid}`,
    source_url: `https://youtu.be/${vid}`,
    meta: { approval_status: 'pending', inserted_by: 'ui-videos-realtime-smoke' },
  };

  const resp = await fetch(`${rest.replace(/\/$/, '')}/videos`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'apikey': key,
      'authorization': `Bearer ${key}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Insert failed (${resp.status}): ${text}`);
  }
  return { vid, title: body.title };
}

test.describe('Videos Realtime', () => {
  test('inserts row and appears in UI', async ({ page }) => {
    const base = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3001';
    const { title } = await insertSmokeRow();

    await page.goto(`${base}/dashboard/videos`);
    // Wait for the new row to appear via Realtime (up to 10s)
    await expect(page.getByText(title)).toBeVisible({ timeout: 10_000 });
  });
});

