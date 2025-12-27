/* ═══════════════════════════════════════════════════════════════════════════
   API: Services Catalog
   Returns the complete service catalog with optional filtering
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import {
  SERVICE_CATALOG,
  SERVICES_BY_CATEGORY,
  getServiceBySlug,
  getServicesByCategory,
  type ServiceCategory,
} from '@/lib/serviceCatalog';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

/**
 * GET /api/services
 * Query params:
 *   - category: Filter by category (observability, database, data, etc.)
 *   - slug: Get single service by slug
 *   - search: Search in title/summary
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const category = searchParams.get('category') as ServiceCategory | null;
  const slug = searchParams.get('slug');
  const searchQuery = searchParams.get('search');

  // Cache for 10 seconds to allow fresh health data
  const headers = {
    'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30',
    'Content-Type': 'application/json',
  };

  try {
    // Single service lookup
    if (slug) {
      const service = getServiceBySlug(slug);
      if (!service) {
        return NextResponse.json({ error: 'Service not found' }, { status: 404, headers });
      }
      return NextResponse.json({ service }, { headers });
    }

    let services = SERVICE_CATALOG;

    // Filter by category
    if (category) {
      services = getServicesByCategory(category);
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      services = services.filter(
        (s) =>
          s.title.toLowerCase().includes(query) ||
          s.summary.toLowerCase().includes(query) ||
          s.slug.includes(query)
      );
    }

    // Group by category if no category filter
    const grouped = category
      ? null
      : Object.entries(SERVICES_BY_CATEGORY).reduce((acc, [cat, srvs]) => {
          acc[cat] = srvs.length;
          return acc;
        }, {} as Record<string, number>);

    return NextResponse.json(
      {
        services,
        grouped,
        total: services.length,
        categories: Object.keys(SERVICES_BY_CATEGORY),
      },
      { headers }
    );
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch services', message: String(error) },
      { status: 500, headers }
    );
  }
}
