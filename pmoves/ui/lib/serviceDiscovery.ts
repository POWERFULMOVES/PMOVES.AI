/**
 * PMOVES Service Discovery - Dynamic Service URL Resolution
 *
 * This module provides async service URL resolution with multiple fallback mechanisms:
 * 1. Environment variables (explicit overrides)
 * 2. Supabase service catalog (dynamic, runtime)
 * 3. Static catalog (fallback for development)
 *
 * Usage:
 * ```ts
 * import { getServiceUrl, getServiceInfo } from './lib/serviceDiscovery';
 *
 * // Simple URL resolution
 * const url = await getServiceUrl({ slug: 'hirag-v2', defaultPort: 8086 });
 *
 * // With custom env var
 * const url = await getServiceUrl({
 *   slug: 'custom-service',
 *   envVar: 'CUSTOM_SERVICE_URL',
 *   defaultPort: 9000
 * });
 *
 * // Get full service info
 * const info = await getServiceInfo('hirag-v2');
 * console.log(`${info.name}: ${info.health_check_url}`);
 * ```
 */

import { createClient } from '@supabase/supabase-js';

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════════ */

export type ServiceTier =
  | 'data'
  | 'api'
  | 'llm'
  | 'worker'
  | 'media'
  | 'agent'
  | 'ui';

export interface ServiceConfig {
  /** Service slug for identification (e.g., "hirag-v2") */
  slug: string;
  /** Default service port (for Docker DNS fallback) */
  defaultPort?: number;
  /** Environment variable name for explicit URL override */
  envVar?: string;
  /** Optional path to append to resolved URL */
  path?: string;
}

export interface ServiceInfo {
  /** Service slug */
  slug: string;
  /** Human-readable name */
  name: string;
  /** Service description */
  description: string;
  /** Health check endpoint URL */
  health_check_url: string;
  /** Default port */
  default_port?: number;
  /** Environment variable for override */
  env_var?: string;
  /** Service tier */
  tier: ServiceTier;
  /** Additional tags */
  tags: Record<string, unknown>;
  /** Extended metadata */
  metadata: Record<string, unknown>;
  /** Whether service is active */
  active: boolean;
}

export interface ServiceDiscoveryOptions {
  /** Supabase client URL (defaults to NEXT_PUBLIC_SUPABASE_URL) */
  supabaseUrl?: string;
  /** Supabase anon key (defaults to NEXT_PUBLIC_SUPABASE_ANON_KEY) */
  supabaseAnonKey?: string;
  /** Whether to throw in production if service not found */
  failFast?: boolean;
  /** Cache TTL in milliseconds (default: 60000 = 1 minute) */
  cacheTtl?: number;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Cache Implementation
   ═══════════════════════════════════════════════════════════════════════════ */

interface CachedUrl {
  url: string;
  timestamp: number;
}

const serviceCache = new Map<string, CachedUrl>();
const DEFAULT_CACHE_TTL = 60000; // 1 minute

function getFromCache(key: string, ttl: number): string | null {
  const cached = serviceCache.get(key);
  if (!cached) return null;

  const now = Date.now();
  if (now - cached.timestamp > ttl) {
    serviceCache.delete(key);
    return null;
  }

  return cached.url;
}

function setCache(key: string, url: string): void {
  serviceCache.set(key, {
    url,
    timestamp: Date.now(),
  });
}

function clearCache(slug?: string): void {
  if (slug) {
    serviceCache.delete(slug);
  } else {
    serviceCache.clear();
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Environment Variable Resolution
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Resolve service URL from environment variable.
 * Checks multiple patterns for the environment variable name.
 *
 * @param config - Service configuration
 * @returns URL from environment or null
 */
export function getUrlFromEnv(config: ServiceConfig): string | null {
  if (typeof window === 'undefined') {
    // Server-side: check process.env
    const patterns = [
      config.envVar,
      `NEXT_PUBLIC_${config.envVar}`,
      config.slug.toUpperCase().replace(/-/g, '_') + '_URL',
      `NEXT_PUBLIC_${config.slug.toUpperCase().replace(/-/g, '_')}_URL`,
    ];

    for (const pattern of patterns) {
      if (pattern && process.env[pattern]) {
        return process.env[pattern];
      }
    }
  } else {
    // Client-side: check import.meta.env
    const patterns = [
      config.envVar,
      `NEXT_PUBLIC_${config.envVar}`,
      config.slug.toUpperCase().replace(/-/g, '_') + '_URL',
      `NEXT_PUBLIC_${config.slug.toUpperCase().replace(/-/g, '_')}_URL`,
    ];

    for (const pattern of patterns) {
      // @ts-expect-error - dynamic env access
      if (pattern && import.meta.env[pattern]) {
        // @ts-expect-error - dynamic env access
        return import.meta.env[pattern];
      }
    }
  }

  return null;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Supabase Service Catalog Resolution
   ═══════════════════════════════════════════════════════════════════════════ */

async function fetchFromSupabase(
  slug: string,
  options?: ServiceDiscoveryOptions
): Promise<ServiceInfo | null> {
  const supabaseUrl =
    options?.supabaseUrl ||
    (typeof process !== 'undefined'
      ? process.env.NEXT_PUBLIC_SUPABASE_URL
      : // @ts-expect-error - dynamic env access
        import.meta.env.NEXT_PUBLIC_SUPABASE_URL);

  const supabaseAnonKey =
    options?.supabaseAnonKey ||
    (typeof process !== 'undefined'
      ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
      : // @ts-expect-error - dynamic env access
        import.meta.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);

  if (!supabaseUrl || !supabaseAnonKey) {
    return null;
  }

  try {
    const supabase = createClient(supabaseUrl, supabaseAnonKey);

    const { data, error } = await supabase
      .from('service_catalog')
      .select('*')
      .eq('slug', slug)
      .eq('active', true)
      .maybe_single();

    if (error || !data) {
      return null;
    }

    return {
      slug: data.slug,
      name: data.name,
      description: data.description || '',
      health_check_url: data.health_check_url,
      default_port: data.default_port,
      env_var: data.env_var,
      tier: data.tier,
      tags: (data.tags as Record<string, unknown>) || {},
      metadata: (data.metadata as Record<string, unknown>) || {},
      active: data.active ?? true,
    };
  } catch {
    // Supabase query failed - fallback to static
    return null;
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Main Resolution Functions
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Resolve service URL using fallback chain.
 *
 * Resolution order:
 * 1. Environment variable (explicit override)
 * 2. Supabase service catalog (dynamic, cached)
 * 3. Docker DNS fallback (development only)
 *
 * @param config - Service configuration
 * @param options - Discovery options
 * @returns Resolved service URL
 *
 * @throws Error if service cannot be resolved in production with failFast=true
 *
 * @example
 * ```ts
 * // Basic usage
 * const url = await getServiceUrl({ slug: 'hirag-v2', defaultPort: 8086 });
 *
 * // With custom env var
 * const url = await getServiceUrl({
 *   slug: 'custom',
 *   envVar: 'CUSTOM_API_URL',
 *   defaultPort: 9000
 * });
 *
 * // With path
 * const url = await getServiceUrl({
 *   slug: 'agent-zero',
 *   path: '/mcp/tools',
 *   defaultPort: 8080
 * });
 * ```
 */
export async function getServiceUrl(
  config: ServiceConfig,
  options?: ServiceDiscoveryOptions
): Promise<string> {
  const { slug, defaultPort = 80, path = '' } = config;
  const cacheKey = slug;
  const cacheTtl = options?.cacheTtl ?? DEFAULT_CACHE_TTL;

  // 1. Check cache first
  const cached = getFromCache(cacheKey, cacheTtl);
  if (cached) {
    return cached + path;
  }

  // 2. Try environment variable override
  const envUrl = getUrlFromEnv(config);
  if (envUrl) {
    const url = envUrl.replace(/\/$/, '') + path;
    setCache(cacheKey, url);
    return url;
  }

  // 3. Try Supabase service catalog
  const serviceInfo = await fetchFromSupabase(slug, options);
  if (serviceInfo) {
    // Use health_check_url but remove /healthz suffix if present
    let url = serviceInfo.health_check_url;
    for (const suffix of ['/healthz', '/health', '/metrics', '/ping']) {
      if (url.endsWith(suffix)) {
        url = url.slice(0, -suffix.length);
        break;
      }
    }
    url = url.replace(/\/$/, '') + path;
    setCache(cacheKey, url);
    return url;
  }

  // 4. Fail fast in production
  const isProduction =
    (typeof process !== 'undefined' ? process.env.NODE_ENV : '') === 'production';

  if (isProduction && options?.failFast !== false) {
    const envName = config.envVar || `NEXT_PUBLIC_${slug.toUpperCase().replace(/-/g, '_')}_URL`;
    throw new Error(
      `Service URL for '${slug}' not configured. ` +
      `Set ${envName} environment variable or ensure service exists in catalog.`
    );
  }

  // 5. Development fallback (Docker DNS)
  const fallbackUrl = `http://${slug}:${defaultPort}${path}`;
  setCache(cacheKey, fallbackUrl);
  return fallbackUrl;
}

/**
 * Get complete service information from the service catalog.
 *
 * @param slug - Service slug to look up
 * @param options - Discovery options
 * @returns Service info or null if not found
 *
 * @example
 * ```ts
 * const info = await getServiceInfo('hirag-v2');
 * if (info) {
 *   console.log(`${info.name} is ${info.tier} tier`);
 *   console.log(`Health: ${info.health_check_url}`);
 * }
 * ```
 */
export async function getServiceInfo(
  slug: string,
  options?: ServiceDiscoveryOptions
): Promise<ServiceInfo | null> {
  // Try Supabase first
  const serviceInfo = await fetchFromSupabase(slug, options);
  if (serviceInfo) {
    return serviceInfo;
  }

  // Return null if not found (let caller handle fallback)
  return null;
}

/**
 * Get all services from a specific tier.
 *
 * @param tier - Service tier to filter by
 * @param options - Discovery options
 * @returns Array of service info objects
 *
 * @example
 * ```ts
 * const agentServices = await getServicesByTier('agent');
 * console.log(`Found ${agentServices.length} agent services`);
 * ```
 */
export async function getServicesByTier(
  tier: ServiceTier,
  options?: ServiceDiscoveryOptions
): Promise<ServiceInfo[]> {
  const supabaseUrl =
    options?.supabaseUrl ||
    (typeof process !== 'undefined'
      ? process.env.NEXT_PUBLIC_SUPABASE_URL
      : import.meta.env?.NEXT_PUBLIC_SUPABASE_URL);

  const supabaseAnonKey =
    options?.supabaseAnonKey ||
    (typeof process !== 'undefined'
      ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
      : import.meta.env?.NEXT_PUBLIC_SUPABASE_ANON_KEY);

  if (!supabaseUrl || !supabaseAnonKey) {
    return [];
  }

  try {
    const supabase = createClient(supabaseUrl, supabaseAnonKey);

    const { data, error } = await supabase
      .from('service_catalog')
      .select('*')
      .eq('tier', tier)
      .eq('active', true)
      .order('slug');

    if (error || !data) {
      return [];
    }

    return data.map((item: unknown) => {
      const d = item as Record<string, unknown>;
      return {
        slug: d.slug as string,
        name: d.name as string,
        description: (d.description as string | undefined) ?? '',
        health_check_url: d.health_check_url as string,
        default_port: d.default_port as number | undefined,
        env_var: d.env_var as string | undefined,
        tier: d.tier as ServiceTier,
        tags: (d.tags as Record<string, unknown>) || {},
        metadata: (d.metadata as Record<string, unknown>) || {},
        active: (d.active as boolean | undefined) ?? true,
      };
    });
  } catch {
    return [];
  }
}

/**
 * Check if a service is healthy by calling its health endpoint.
 *
 * @param config - Service configuration
 * @param options - Discovery options
 * @returns True if service is healthy, false otherwise
 *
 * @example
 * ```ts
 * const isHealthy = await checkServiceHealth(
 *   { slug: 'hirag-v2', defaultPort: 8086 }
 * );
 * if (!isHealthy) {
 *   console.error('Service is down!');
 * }
 * ```
 */
export async function checkServiceHealth(
  config: ServiceConfig,
  options?: ServiceDiscoveryOptions
): Promise<boolean> {
  try {
    const healthUrl = await getServiceUrl(
      { ...config, path: '' },
      options
    );

    // Append /healthz or /health if path not already present
    let finalUrl = healthUrl;
    if (!finalUrl.includes('/healthz') && !finalUrl.includes('/health')) {
      finalUrl = finalUrl.replace(/\/$/, '') + '/healthz';
    }

    const response = await fetch(finalUrl, {
      method: 'GET',
      signal: AbortSignal.timeout(5000), // 5 second timeout
    });

    return response.ok;
  } catch {
    return false;
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Cache Management
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Clear cached service URL(s).
 *
 * @param slug - Optional service slug to clear. If omitted, clears all cache.
 *
 * @example
 * ```ts
 * // Clear specific service
 * clearServiceCache('hirag-v2');
 *
 * // Clear all cache
 * clearServiceCache();
 * ```
 */
export function clearServiceCache(slug?: string): void {
  clearCache(slug);
}

/* ═══════════════════════════════════════════════════════════════════════════
   Utility Functions
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Resolve multiple service URLs in parallel.
 *
 * @param configs - Array of service configurations
 * @param options - Discovery options
 * @returns Map of slug to resolved URL
 *
 * @example
 * ```ts
 * const urls = await resolveMultipleServiceUrls([
 *   { slug: 'hirag-v2', defaultPort: 8086 },
 *   { slug: 'agent-zero', defaultPort: 8080 },
 *   { slug: 'tensorzero', defaultPort: 3030 },
 * ]);
 * console.log(urls.get('hirag-v2')); // "http://hi-rag-gateway-v2:8086"
 * ```
 */
export async function resolveMultipleServiceUrls(
  configs: ServiceConfig[],
  options?: ServiceDiscoveryOptions
): Promise<Map<string, string>> {
  const results = await Promise.all(
    configs.map(async (config) => {
      const url = await getServiceUrl(config, options);
      return [config.slug, url] as const;
    })
  );

  return new Map(results);
}

/**
 * Create a pre-configured service URL resolver for a specific service.
 *
 * @param config - Service configuration
 * @param options - Discovery options
 * @returns Function that resolves the service URL
 *
 * @example
 * ```ts
 * const getHiragUrl = createServiceUrlResolver({
 *   slug: 'hirag-v2',
 *   defaultPort: 8086
 * });
 *
 * // Later
 * const url = await getHiragUrl();
 * ```
 */
export function createServiceUrlResolver(
  config: ServiceConfig,
  options?: ServiceDiscoveryOptions
): () => Promise<string> {
  return () => getServiceUrl(config, options);
}

/* ═══════════════════════════════════════════════════════════════════════════
   Module Exports
   ═══════════════════════════════════════════════════════════════════════════ */

export {
  // Main functions
  getServiceUrl,
  getServiceInfo,
  getServicesByTier,
  checkServiceHealth,
  resolveMultipleServiceUrls,
  createServiceUrlResolver,

  // Utility functions
  clearServiceCache,
  getUrlFromEnv,

  // Types
  type ServiceConfig,
  type ServiceInfo,
  type ServiceDiscoveryOptions,
  type ServiceTier,
};
