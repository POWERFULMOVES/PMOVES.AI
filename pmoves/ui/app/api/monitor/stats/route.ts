import { NextRequest, NextResponse } from 'next/server';
import { authenticateRequest } from '@/lib/jwtUtils';
import { logError } from '@/lib/errorUtils';
import { ErrorIds } from '@/lib/constants/errorIds';

const UPSTREAM = (process.env.CHANNEL_MONITOR_STATS_URL || process.env.NEXT_PUBLIC_CHANNEL_MONITOR_STATS_URL || 'http://localhost:8097/api/monitor/stats');

export async function GET(req: NextRequest) {
  const { ownerId, error: authError } = authenticateRequest(req, 'monitor/stats');
  if (!ownerId) {
    return NextResponse.json({ error: authError || 'Authentication required' }, { status: 401 });
  }

  try {
    const res = await fetch(UPSTREAM, { cache: 'no-store' });
    const text = await res.text();
    const body = (() => { try { return JSON.parse(text); } catch { return { raw: text }; } })();
    return NextResponse.json(body, { status: res.status });
  } catch (e) {
    logError('Failed to fetch monitor stats', e, 'error', {
      errorId: ErrorIds.MONITOR_STATS_FETCH_FAILED,
      component: 'monitor/stats',
    });
    return NextResponse.json({ error: 'Service temporarily unavailable' }, { status: 502 });
  }
}
