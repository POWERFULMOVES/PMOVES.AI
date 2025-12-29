/* ═══════════════════════════════════════════════════════════════════════════
   API: Health Check
   Returns health status for all or specific services
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import { checkAllServices, checkServiceHealth, getHealthPercentage, getStatusText } from '@/lib/serviceHealth';

export const runtime = 'edge';
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
  const searchParams = request.nextUrl.searchParams;
  const timeout = parseInt(searchParams.get('timeout') || '5000', 10);
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
    return NextResponse.json(
      {
        error: 'Health check failed',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500, headers }
    );
  }
}
