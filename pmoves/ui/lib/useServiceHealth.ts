/* ═══════════════════════════════════════════════════════════════════════════
   React Hook: Service Health Polling
   Auto-refreshing health status for services
   ═══════════════════════════════════════════════════════════════════════════ */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { ServiceHealthMap, ServiceHealthStatus } from './serviceHealth';

export interface UseServiceHealthOptions {
  pollInterval?: number; // Polling interval in ms (default: 30000)
  timeout?: number; // Health check timeout in ms (default: 5000)
  tier?: string; // Filter by category/tier
  enabled?: boolean; // Enable/disable polling (default: true)
}

export interface UseServiceHealthResult {
  health: ServiceHealthMap;
  status: 'idle' | 'loading' | 'success' | 'error';
  error: string | null;
  isPolling: boolean;
  refresh: () => Promise<void>;
  lastUpdate: Date | null;
}

/**
 * React hook for polling service health status
 *
 * @example
 * const { health, isPolling, refresh } = useServiceHealth({ pollInterval: 30000 });
 */
export function useServiceHealth(options: UseServiceHealthOptions = {}): UseServiceHealthResult {
  const {
    pollInterval = 30000,
    timeout = 5000,
    tier,
    enabled = true,
  } = options;

  const [health, setHealth] = useState<ServiceHealthMap>({});
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  /**
   * Fetch health status from API
   */
  const fetchHealth = useCallback(async () => {
    if (!mountedRef.current) return;

    setStatus('loading');
    setError(null);

    try {
      const params = new URLSearchParams();
      if (tier) params.set('tier', tier);
      params.set('timeout', timeout.toString());

      const response = await fetch(`/api/services-hub?${params.toString()}`);

      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`);
      }

      const data = await response.json();

      if (!mountedRef.current) return;

      // Extract health from hub response
      if (data.health?.services) {
        const healthMap: ServiceHealthMap = {};
        for (const service of data.health.services) {
          healthMap[service.slug] = {
            status: service.status,
            responseTime: service.responseTime,
          };
        }
        setHealth(healthMap);
        setLastUpdate(new Date());
        setStatus('success');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      setStatus('error');
    }
  }, [timeout, tier]);

  /**
   * Manual refresh function
   */
  const refresh = useCallback(async () => {
    await fetchHealth();
  }, [fetchHealth]);

  /**
   * Set up polling interval
   */
  useEffect(() => {
    if (!enabled) return;

    setIsPolling(true);

    // Initial fetch
    fetchHealth();

    // Set up interval
    intervalRef.current = setInterval(() => {
      fetchHealth();
    }, pollInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled, pollInterval, fetchHealth]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return {
    health,
    status,
    error,
    isPolling,
    refresh,
    lastUpdate,
  };
}

/**
 * Get health status for a specific service
 */
export function getServiceStatus(
  health: ServiceHealthMap,
  slug: string
): ServiceHealthStatus {
  return health[slug]?.status || 'unknown';
}

/**
 * Check if a service is healthy
 */
export function isServiceHealthy(health: ServiceHealthMap, slug: string): boolean {
  return health[slug]?.status === 'healthy';
}

/**
 * Get all healthy services
 */
export function getHealthyServices(health: ServiceHealthMap): string[] {
  return Object.entries(health)
    .filter(([_, h]) => h.status === 'healthy')
    .map(([slug, _]) => slug);
}

/**
 * Get all unhealthy services
 */
export function getUnhealthyServices(health: ServiceHealthMap): string[] {
  return Object.entries(health)
    .filter(([_, h]) => h.status === 'unhealthy')
    .map(([slug, _]) => slug);
}
