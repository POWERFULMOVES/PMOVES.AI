/* ═══════════════════════════════════════════════════════════════════════════
   API: Services Hub
   Aggregates service catalog + health + tier stats for the central dashboard
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import { checkAllServices, getHealthPercentage, type HealthCheckResult } from '@/lib/serviceHealth';
import { SERVICE_CATALOG, type ServiceCategory, type ServiceDefinition } from '@/lib/serviceCatalog';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

/**
 * Tier statistics for a category
 */
interface TierStats {
  total: number;
  healthy: number;
  unhealthy: number;
  unknown: number;
  percentage: number;
}

/**
 * Hub data response
 */
interface HubData {
  services: ServiceDefinition[];
  health: HealthCheckResult;
  tiers: Record<ServiceCategory, TierStats>;
  stats: {
    totalServices: number;
    healthyPercentage: number;
    criticalDown: string[];
  };
}

/**
 * Calculate tier statistics from health check results
 */
function calculateTierStats(
  healthResult: HealthCheckResult
): Record<ServiceCategory, TierStats> {
  const categories: ServiceCategory[] = [
    'observability', 'database', 'data', 'bus', 'workers',
    'agents', 'gpu', 'media', 'llm', 'ui', 'integration'
  ];

  const tierStats: Record<string, TierStats> = {};

  // Initialize all categories
  for (const category of categories) {
    tierStats[category] = {
      total: 0,
      healthy: 0,
      unhealthy: 0,
      unknown: 0,
      percentage: 0,
    };
  }

  // Count services by category and health status
  const healthMap = new Map(healthResult.services.map(h => [h.slug, h]));

  for (const service of SERVICE_CATALOG) {
    const stats = tierStats[service.category];
    if (stats) {
      stats.total++;
      const health = healthMap.get(service.slug);
      if (health) {
        if (health.status === 'healthy') stats.healthy++;
        else if (health.status === 'unhealthy') stats.unhealthy++;
        else stats.unknown++;
      } else {
        stats.unknown++;
      }
    }
  }

  // Calculate percentages
  for (const category of categories) {
    const stats = tierStats[category];
    if (stats.total > 0) {
      stats.percentage = Math.round((stats.healthy / stats.total) * 100);
    }
  }

  return tierStats as Record<ServiceCategory, TierStats>;
}

/**
 * Identify critical services that are down
 */
function getCriticalDownServices(
  healthResult: HealthCheckResult,
  tierStats: Record<ServiceCategory, TierStats>
): string[] {
  const criticalSlugs = [
    'prometheus',      // Observability foundation
    'postgres',        // Primary database
    'nats',            // Message bus
    'agent-zero',      // Orchestrator
    'tensorzero',      // LLM gateway
    'hi-rag-v2',       // Knowledge retrieval
  ];

  const healthMap = new Map(healthResult.services.map(h => [h.slug, h]));
  const down: string[] = [];

  for (const slug of criticalSlugs) {
    const health = healthMap.get(slug);
    if (health && health.status === 'unhealthy') {
      down.push(slug);
    }
  }

  return down;
}

/**
 * GET /api/services-hub
 *
 * Query params:
 *   - timeout: Health check timeout in ms (default: 3000)
 *   - tier: Filter by category/tier
 *   - simple: Skip health checks, return catalog only
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const timeout = parseInt(searchParams.get('timeout') || '3000', 10);
  const tier = searchParams.get('tier') as ServiceCategory | null;
  const simple = searchParams.get('simple') === 'true';

  try {
    // Filter services by tier if specified
    let services = SERVICE_CATALOG;
    if (tier) {
      services = services.filter(s => s.category === tier);
    }

    // If simple mode, return catalog without health checks
    if (simple) {
      return NextResponse.json({
        services,
        timestamp: new Date(),
        total: services.length,
      }, {
        headers: {
          'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120',
        },
      });
    }

    // Perform health checks
    const health = await checkAllServices(timeout, tier ? { category: tier } : undefined);

    // Calculate tier statistics
    const tiers = calculateTierStats(health);

    // Identify critical services that are down
    const criticalDown = getCriticalDownServices(health, tiers);

    const hubData: HubData = {
      services,
      health,
      tiers,
      stats: {
        totalServices: health.total,
        healthyPercentage: getHealthPercentage(health),
        criticalDown,
      },
    };

    return NextResponse.json(hubData, {
      headers: {
        // Cache catalog data, but not health
        'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30',
        'Content-Type': 'application/json',
      },
    });

  } catch (error) {
    return NextResponse.json(
      {
        error: 'Services hub request failed',
        message: error instanceof Error ? error.message : String(error),
        services: SERVICE_CATALOG.filter(tier ? s => s.category === tier : () => true),
        health: null,
        tiers: {},
        stats: null,
      },
      { status: 500 }
    );
  }
}
