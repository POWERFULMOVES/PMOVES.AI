import { NextRequest, NextResponse } from 'next/server';

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
      { status: 200 }
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
      console.error('[notebook-sources-api]', `HTTP ${res.status}:`, errorText, { endpoint });
      return NextResponse.json(
        { items: [], error: `Open Notebook API returned ${res.status}` },
        { status: 200 }
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
    console.error('[notebook-sources-api]', 'Fetch error:', err, { endpoint });
    return NextResponse.json(
      { items: [], error: 'Failed to fetch sources from Open Notebook' },
      { status: 200 }
    );
  }
}
