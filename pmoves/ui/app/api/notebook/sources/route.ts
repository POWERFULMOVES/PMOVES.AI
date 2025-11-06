import { NextRequest, NextResponse } from 'next/server';

let NB = (process.env.OPEN_NOTEBOOK_API_URL || process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_API_URL || '').replace(/\/$/, '');
if (NB.includes('cataclysm-open-notebook')) {
  NB = 'http://localhost:5055';
}

export async function GET(_req: NextRequest) {
  if (!NB) return NextResponse.json({ items: [], error: 'OPEN_NOTEBOOK_API_URL not set' }, { status: 200 });
  // Try a few likely endpoints; return first that works
  const attempts = [
    `${NB}/sources?limit=10`,
    `${NB}/items?limit=10`,
  ];
  for (const url of attempts) {
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) continue;
      const json = await res.json();
      const items = Array.isArray(json?.items) ? json.items : Array.isArray(json) ? json : [];
      if (items.length) return NextResponse.json({ items, endpoint: url });
    } catch {}
  }
  return NextResponse.json({ items: [] }, { status: 200 });
}
