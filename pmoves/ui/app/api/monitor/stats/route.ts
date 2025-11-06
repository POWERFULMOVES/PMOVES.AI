import { NextRequest, NextResponse } from 'next/server';

const UPSTREAM = (process.env.CHANNEL_MONITOR_STATS_URL || process.env.NEXT_PUBLIC_CHANNEL_MONITOR_STATS_URL || 'http://localhost:8097/api/monitor/stats');

export async function GET(_req: NextRequest) {
  try {
    const res = await fetch(UPSTREAM, { cache: 'no-store' });
    const text = await res.text();
    const body = (() => { try { return JSON.parse(text); } catch { return { raw: text }; } })();
    return NextResponse.json(body, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || String(e) }, { status: 502 });
  }
}

