/* ═══════════════════════════════════════════════════════════════════════════
   API: Health Check
   Returns health status for all or specific services
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import { checkAllServices, checkServiceHealth, getHealthPercentage, getStatusText } from '@/lib/serviceHealth';
import { authenticateRequest } from '@/lib/jwtUtils';
import { logError } from '@/lib/errorUtils';

// NOTE: Using 'nodejs' runtime instead of 'edge' because Edge runtime
// doesn't support localhost DNS resolution, which is needed for service
// health checks within the Docker network.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * GET /api/health-all
 * Query params:
 *   - timeout: Request timeout in ms (default: 5000)
 *   - category: Filter by category
 *   - slugs: Comma-separated list of service slugs
 *   - simple: Return simplified status (for quick checks)
 */
export async function GET(request: NextRequest) {
  const { ownerId, error: authError } = authenticateRequest(request, 'health-all');
  if (!ownerId) {
    return NextResponse.json({ error: authError || 'Authentication required' }, { status: 401 });
  }

  const searchParams = request.nextUrl.searchParams;
  const rawTimeout = parseInt(searchParams.get('timeout') || '5000', 10);
  const timeout = Number.isFinite(rawTimeout) && rawTimeout > 0
    ? Math.min(Math.max(rawTimeout, 1000), 30_000)
    : 5000;
  const category = searchParams.get('category') || undefined;
  const slugsParam = searchParams.get('slugs');
  const simple = searchParams.get('simple') === 'true';

  const headers = {
    // Don't cache health checks
    'Cache-Control': 'no-store, no-cache, must-revalidate',
    'Content-Type': 'application/json',
  };

  try {
    // Single service check
    if (slugsParam && slugsParam.split(',').length === 1) {
      const slug = slugsParam;
      const health = await checkServiceHealth(slug);

      if (!health) {
        return NextResponse.json({ error: 'Service not found' }, { status: 404, headers });
      }

      return simple
        ? NextResponse.json(
            { slug: health.slug, status: health.status, text: getStatusText(health.status) },
            { headers }
          )
        : NextResponse.json({ health }, { headers });
    }

    // Multiple services or all
    const filter: { category?: string; slugs?: string[] } = {};
    if (category) filter.category = category;
    if (slugsParam) filter.slugs = slugsParam.split(',');

    const result = await checkAllServices(timeout, Object.keys(filter).length > 0 ? filter : undefined);

    if (simple) {
      const simpleServices = result.services.map((s) => ({
        slug: s.slug,
        status: s.status,
        text: getStatusText(s.status),
      }));

      return NextResponse.json(
        {
          services: simpleServices,
          percentage: getHealthPercentage(result),
          timestamp: result.timestamp,
        },
        { headers }
      );
    }

    return NextResponse.json(
      {
        ...result,
        percentage: getHealthPercentage(result),
      },
      { headers }
    );
  } catch (error) {
    logError('Health check aggregation failed', error, 'error', {
      component: 'health-all',
    });
    return NextResponse.json(
      { error: 'Health check failed' },
      { status: 500, headers }
    );
  }
}
