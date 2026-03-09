import type { NextRequest } from 'next/server';
import { GET as getHealthAll } from '../../health-all/route';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

/**
 * Back-compat alias for legacy clients expecting /api/health/all.
 */
export function GET(request: NextRequest) {
  return getHealthAll(request);
}
