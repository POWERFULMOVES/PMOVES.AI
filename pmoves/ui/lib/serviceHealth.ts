/* ═══════════════════════════════════════════════════════════════════════════
   PMOVES Service Health Checker
   Real-time health monitoring for all services
   Cataclysm Studios Inc.
   ═══════════════════════════════════════════════════════════════════════════ */

import { SERVICE_CATALOG, type ServiceDefinition } from './serviceCatalog';

export type ServiceHealthStatus = 'healthy' | 'unhealthy' | 'unknown' | 'checking';

export interface ServiceHealth {
  slug: string;
  status: ServiceHealthStatus;
  responseTime?: number; // ms
  lastCheck: Date;
  error?: string;
}

// Simplified health map for components (indexable object)
export interface ServiceHealthMap {
  [slug: string]: {
    status: ServiceHealthStatus;
    responseTime?: number;
  };
}

export interface HealthCheckResult {
  services: ServiceHealth[];
  timestamp: Date;
  total: number;
  healthy: number;
  unhealthy: number;
  unknown: number;
}

/**
 * Probe a single service health endpoint
 */
export async function probeService(
  service: ServiceDefinition,
  timeout = 5000
): Promise<ServiceHealth> {
  const startTime = performance.now();

  // If service has no health check, mark as unknown
  if (!service.healthCheck) {
    return {
      slug: service.slug,
      status: 'unknown',
      lastCheck: new Date(),
    };
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const response = await fetch(service.healthCheck, {
      method: 'GET',
      signal: controller.signal,
      // Don't cache health checks
      cache: 'no-store',
    });

    clearTimeout(timeoutId);

    const responseTime = performance.now() - startTime;

    return {
      slug: service.slug,
      status: response.ok ? 'healthy' : 'unhealthy',
      responseTime: Math.round(responseTime),
      lastCheck: new Date(),
      error: response.ok ? undefined : `HTTP ${response.status}`,
    };
  } catch (error) {
    const responseTime = performance.now() - startTime;

    return {
      slug: service.slug,
      status: 'unhealthy',
      responseTime: Math.round(responseTime),
      lastCheck: new Date(),
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Check health of all services in parallel
 */
export async function checkAllServices(
  timeout = 5000,
  filter?: { category?: string; slugs?: string[] }
): Promise<HealthCheckResult> {
  let servicesToCheck = SERVICE_CATALOG;

  // Apply filters
  if (filter?.category) {
    servicesToCheck = servicesToCheck.filter((s) => s.category === filter.category);
  }
  if (filter?.slugs) {
    servicesToCheck = servicesToCheck.filter((s) => filter.slugs!.includes(s.slug));
  }

  // Check all services in parallel (batched to avoid overwhelming)
  const batchSize = 20;
  const results: ServiceHealth[] = [];

  for (let i = 0; i < servicesToCheck.length; i += batchSize) {
    const batch = servicesToCheck.slice(i, i + batchSize);
    const batchResults = await Promise.all(
      batch.map((service) => probeService(service, timeout))
    );
    results.push(...batchResults);
  }

  // Calculate statistics
  const healthy = results.filter((r) => r.status === 'healthy').length;
  const unhealthy = results.filter((r) => r.status === 'unhealthy').length;
  const unknown = results.filter((r) => r.status === 'unknown').length;

  return {
    services: results,
    timestamp: new Date(),
    total: results.length,
    healthy,
    unhealthy,
    unknown,
  };
}

/**
 * Check health of a single service by slug
 */
export async function checkServiceHealth(slug: string): Promise<ServiceHealth | undefined> {
  const service = SERVICE_CATALOG.find((s) => s.slug === slug);
  if (!service) return undefined;

  return probeService(service);
}

/**
 * Get health status as a percentage (0-100)
 */
export function getHealthPercentage(result: HealthCheckResult): number {
  if (result.total === 0) return 0;
  return Math.round((result.healthy / result.total) * 100);
}

/**
 * Get status badge class for Tailwind
 */
export function getStatusBadgeClass(status: ServiceHealthStatus): string {
  const base = 'font-pixel text-[6px] uppercase px-2 py-1';
  switch (status) {
    case 'healthy':
      return `${base} text-cata-forest bg-cata-forest/10`;
    case 'unhealthy':
      return `${base} text-cata-ember bg-cata-ember/10`;
    case 'checking':
      return `${base} text-cata-gold bg-cata-gold/10`;
    default:
      return `${base} text-ink-muted bg-void-soft`;
  }
}

/**
 * Get status indicator color
 */
export function getStatusIndicatorClass(status: ServiceHealthStatus): string {
  switch (status) {
    case 'healthy':
      return 'w-2 h-2 bg-cata-forest animate-pulse';
    case 'unhealthy':
      return 'w-2 h-2 bg-cata-ember';
    case 'checking':
      return 'w-2 h-2 bg-cata-gold animate-spin';
    default:
      return 'w-2 h-2 bg-ink-muted';
  }
}

/**
 * Format response time for display
 */
export function formatResponseTime(ms?: number): string {
  if (ms === undefined) return '--';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Get status text for display
 */
export function getStatusText(status: ServiceHealthStatus): string {
  switch (status) {
    case 'healthy':
      return 'Online';
    case 'unhealthy':
      return 'Offline';
    case 'checking':
      return 'Checking...';
    default:
      return 'Unknown';
  }
}

/**
 * Create a health map for quick lookup
 */
export function createHealthMap(result: HealthCheckResult): ServiceHealthMap {
  const map: ServiceHealthMap = {};
  for (const health of result.services) {
    map[health.slug] = {
      status: health.status,
      responseTime: health.responseTime,
    };
  }
  return map;
}
