import { NextRequest, NextResponse } from 'next/server';
import { logError } from '@/lib/errorUtils';

// Open Notebook API endpoint - documented in docs/services/open-notebook/
const NOTEBOOK_API_URL = (
  process.env.OPEN_NOTEBOOK_API_URL ||
  process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_API_URL ||
  ''
).replace(/\/$/, '');

const NOTEBOOK_API_TOKEN = process.env.OPEN_NOTEBOOK_API_TOKEN || '';

export async function GET(_req: NextRequest) {
  // Check configuration
  if (!NOTEBOOK_API_URL) {
    return NextResponse.json(
      { items: [], error: 'OPEN_NOTEBOOK_API_URL not configured' },
      { status: 503 }  // Service Unavailable - configuration missing
    );
  }

  const endpoint = `${NOTEBOOK_API_URL}/api/sources`;

  try {
    const headers: HeadersInit = {
      'Accept': 'application/json',
    };
    if (NOTEBOOK_API_TOKEN) {
      headers['Authorization'] = `Bearer ${NOTEBOOK_API_TOKEN}`;
    }

    const res = await fetch(`${endpoint}?limit=10`, {
      headers,
      cache: 'no-store',
    });

    if (!res.ok) {
      const errorText = await res.text().catch(() => 'Unknown error');
      logError(`Open Notebook API returned ${res.status}`, new Error(errorText), 'warning', {
        component: 'notebook-sources-api',
        endpoint,
      });
      return NextResponse.json(
        { items: [], error: `Open Notebook API returned ${res.status}` },
        { status: 502 }  // Bad Gateway - upstream failure
      );
    }

    const json = await res.json();
    // Handle both array response and { items: [...] } wrapper
    const items = Array.isArray(json?.items)
      ? json.items
      : Array.isArray(json)
        ? json
        : [];

    return NextResponse.json({ items, endpoint });
  } catch (err) {
    logError('Failed to fetch sources from Open Notebook', err instanceof Error ? err : new Error(String(err)), 'error', {
      component: 'notebook-sources-api',
      endpoint,
    });
    return NextResponse.json(
      { items: [], error: 'Failed to fetch sources from Open Notebook' },
      { status: 502 }  // Bad Gateway - network/fetch failure
    );
  }
}
