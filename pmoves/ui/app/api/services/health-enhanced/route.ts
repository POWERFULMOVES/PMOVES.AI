/* ═══════════════════════════════════════════════════════════════════════════
   API: Enhanced Service Health
   Extends basic health checks with tier filtering, agent overlay, response time history
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import { checkAllServices, type HealthCheckResult } from '@/lib/serviceHealth';
import { SERVICE_CATALOG, type ServiceDefinition } from '@/lib/serviceCatalog';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

/**
 * Tier to category mapping
 */
const TIER_CATEGORIES: Record<number, string[]> = {
  1: ['data', 'database', 'observability'],
  2: ['api', 'bus', 'llm'],
  3: ['llm'],
  4: ['workers', 'gpu'],
  5: ['media'],
  6: ['agents'],
  7: ['ui'],
};

/**
 * Agent services overlay (services that are agents themselves)
 */
const AGENT_SLUGS = new Set([
  'agent-zero',
  'archon',
  'deepresearch',
  'supaserch',
  'botz-gateway',
  'consciousness-service',
]);

/**
 * Enhanced service health entry
 */
interface EnhancedServiceHealth {
  slug: string;
  title: string;
  category: string;
  tier: number;
  status: 'healthy' | 'unhealthy' | 'unknown' | 'checking';
  responseTime?: number;
  lastCheck: string;
  error?: string;
  isAgent: boolean;
  capabilities: string[];
  endpoints: Array<{
    name: string;
    port: string;
    type: string;
  }>;
}

/**
 * Enhanced health response with tier statistics
 */
interface EnhancedHealthResponse {
  services: EnhancedServiceHealth[];
  tiers: Record<number, {
    total: number;
    healthy: number;
    unhealthy: number;
    unknown: number;
    percentage: number;
  }>;
  agents: {
    total: number;
    healthy: number;
    unhealthy: number;
  };
  responseTimeStats: {
    avg: number;
    min: number;
    max: number;
  };
  timestamp: string;
}

/**
 * GET /api/services/health-enhanced
 *
 * Query params:
 *   - timeout: Health check timeout in ms (default: 5000)
 *   - tier: Filter by tier number (1-7)
 *   - category: Filter by category
 *   - agentsOnly: Return only agent services
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const rawTimeout = parseInt(searchParams.get('timeout') || '5000', 10);
  const timeout = Number.isFinite(rawTimeout) && rawTimeout > 0
    ? Math.min(Math.max(rawTimeout, 1000), 30_000)
    : 5000;
  const tierParam = searchParams.get('tier');
  const categoryParam = searchParams.get('category');
  const agentsOnly = searchParams.get('agentsOnly') === 'true';

  try {
    // Determine which services to check
    let servicesToCheck = SERVICE_CATALOG;

    if (tierParam) {
      const tier = parseInt(tierParam, 10);
      const categories = TIER_CATEGORIES[tier] || [];
      servicesToCheck = servicesToCheck.filter((s) => categories.includes(s.category));
    }

    if (categoryParam) {
      servicesToCheck = servicesToCheck.filter((s) => s.category === categoryParam);
    }

    if (agentsOnly) {
      servicesToCheck = servicesToCheck.filter((s) => AGENT_SLUGS.has(s.slug));
    }

    // Perform health checks
    const healthResult: HealthCheckResult = await checkAllServices(
      timeout,
      categoryParam ? { category: categoryParam as any } : undefined
    );

    // Build enhanced response
    const healthMap = new Map(
      healthResult.services.map((h) => [h.slug, h])
    );

    const services: EnhancedServiceHealth[] = servicesToCheck.map((service) => {
      const health = healthMap.get(service.slug);

      // Determine tier from category
      let tier = 4; // default
      for (const [t, categories] of Object.entries(TIER_CATEGORIES)) {
        if (categories.includes(service.category)) {
          tier = parseInt(t, 10);
          break;
        }
      }

      return {
        slug: service.slug,
        title: service.title,
        category: service.category,
        tier,
        status: health?.status || 'unknown',
        responseTime: health?.responseTime,
        lastCheck: health?.lastCheck instanceof Date
          ? health.lastCheck.toISOString()
          : health?.lastCheck || new Date().toISOString(),
        error: health?.error,
        isAgent: AGENT_SLUGS.has(service.slug),
        capabilities: service.capabilities || [],
        endpoints: service.endpoints.map((e) => ({
          name: e.name,
          port: e.port,
          type: e.type,
        })),
      };
    });

    // Calculate tier statistics
    const tiers: EnhancedHealthResponse['tiers'] = {};
    for (let t = 1; t <= 7; t++) {
      const tierServices = services.filter((s) => s.tier === t);
      const healthy = tierServices.filter((s) => s.status === 'healthy').length;
      const unhealthy = tierServices.filter((s) => s.status === 'unhealthy').length;
      const unknown = tierServices.filter((s) => s.status === 'unknown').length;

      tiers[t] = {
        total: tierServices.length,
        healthy,
        unhealthy,
        unknown,
        percentage: tierServices.length > 0 ? Math.round((healthy / tierServices.length) * 100) : 0,
      };
    }

    // Calculate agent statistics
    const agentServices = services.filter((s) => s.isAgent);
    const agents = {
      total: agentServices.length,
      healthy: agentServices.filter((s) => s.status === 'healthy').length,
      unhealthy: agentServices.filter((s) => s.status === 'unhealthy').length,
    };

    // Calculate response time statistics
    const responseTimes = services
      .map((s) => s.responseTime)
      .filter((rt): rt is number => rt !== undefined);

    const responseTimeStats = {
      avg: responseTimes.length > 0
        ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length)
        : 0,
      min: responseTimes.length > 0 ? Math.min(...responseTimes) : 0,
      max: responseTimes.length > 0 ? Math.max(...responseTimes) : 0,
    };

    const response: EnhancedHealthResponse = {
      services,
      tiers,
      agents,
      responseTimeStats,
      timestamp: new Date().toISOString(),
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'private, no-store, max-age=0',
      },
    });

  } catch (error) {
    return NextResponse.json(
      {
        error: 'Enhanced health check failed',
        message: error instanceof Error ? error.message : String(error),
        services: [],
        tiers: {},
        agents: { total: 0, healthy: 0, unhealthy: 0 },
        responseTimeStats: { avg: 0, min: 0, max: 0 },
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}
