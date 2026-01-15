/* ═══════════════════════════════════════════════════════════════════════════
   Test Helpers for PMOVES UI
   ═══════════════════════════════════════════════════════════════════════════ */

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import type { ServiceHealthStatus } from '../../lib/serviceHealth';
import type { ServiceDefinition, ServiceCategory, ServiceColor } from '../../lib/serviceCatalog';

// =============================================================================
// Mock Factories
// =============================================================================

/**
 * Creates a mock service health object with optional overrides
 */
export function mockServiceHealth(overrides: Partial<ServiceHealthStatus> = {}): ServiceHealthStatus {
  return {
    status: 'healthy',
    responseTime: 50,
    lastCheck: new Date(),
    ...overrides,
  };
}

/**
 * Creates a mock service health map for multiple services
 */
export function mockServiceHealthMap(
  services: Array<{ slug: string; status?: ServiceHealthStatus }>
): Record<string, ServiceHealthStatus> {
  const map: Record<string, ServiceHealthStatus> = {};
  for (const service of services) {
    map[service.slug] = mockServiceHealth(service.status);
  }
  return map;
}

/**
 * Creates a mock service endpoint
 */
export function mockServiceEndpoint(overrides: Partial<{
  name: string;
  port: string;
  path: string;
  type: 'api' | 'ui' | 'health' | 'metrics' | 'ws';
}> = {}) {
  return {
    name: 'API',
    port: '8080',
    path: '/api',
    type: 'api' as const,
    ...overrides,
  };
}

/**
 * Creates a mock service definition
 */
export function mockServiceDefinition(overrides: Partial<{
  slug: string;
  title: string;
  summary: string;
  category: ServiceCategory;
  color: ServiceColor;
  endpoints: Array<{ name: string; port: string; path: string; type: string }>;
  healthCheck: string;
}> = {}): ServiceDefinition {
  return {
    slug: 'test-service',
    title: 'Test Service',
    summary: 'A test service for unit testing',
    category: 'workers',
    color: 'cyan',
    endpoints: [mockServiceEndpoint()],
    healthCheck: '/healthz',
    ...overrides,
  };
}

/**
 * Creates a mock service catalog
 */
export function mockServiceCatalog(count: number = 5): ServiceDefinition[] {
  const categories: ServiceCategory[] = ['observability', 'database', 'data', 'bus', 'workers', 'agents', 'gpu', 'media', 'llm', 'ui', 'integration'];
  const colors: ServiceColor[] = ['cyan', 'ember', 'gold', 'forest', 'violet'];

  return Array.from({ length: count }, (_, i) => mockServiceDefinition({
    slug: `service-${i}`,
    title: `Service ${i}`,
    category: categories[i % categories.length],
    color: colors[i % colors.length],
  }));
}

// =============================================================================
// Custom Render Functions
// =============================================================================

/**
 * Renders a component with auth context wrapper
 */
export function renderWithAuth(
  ui: ReactElement,
  options: Omit<RenderOptions, 'wrapper'> & {
    authOverrides?: {
      session?: { user: { id: string; email: string } } | null;
      loading?: boolean;
    };
  } = {}
) {
  const { authOverrides, ...renderOptions } = options;

  // TODO: Add actual auth context wrapper when available
  return render(ui, renderOptions);
}

/**
 * Renders a component with service health context
 */
export function renderWithServiceHealth(
  ui: ReactElement,
  healthMap: Record<string, ServiceHealthStatus> = {},
  options: Omit<RenderOptions, 'wrapper'> = {}
) {
  // TODO: Add service health context wrapper when available
  return render(ui, options);
}

// =============================================================================
// Test Helpers
// =============================================================================

/**
 * Waits for a health update to complete (for polling tests)
 */
export async function waitForHealthUpdate(
  callback: () => void,
  timeout: number = 100
): Promise<void> {
  await new Promise<void>((resolve) => {
    const startTime = Date.now();

    const checkInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;

      try {
        callback();
        if (elapsed >= timeout) {
          clearInterval(checkInterval);
          resolve();
        }
      } catch {
        if (elapsed >= timeout) {
          clearInterval(checkInterval);
          resolve();
        }
      }
    }, 10);
  });
}

/**
 * Advances timers by a specified amount (for polling tests)
 */
export function advanceTimersBy(ms: number) {
  jest.advanceTimersByTime(ms);
}

/**
 * Fast-forwards timers and runs all pending timers
 */
export function runAllTimers() {
  jest.runAllTimers();
}

// =============================================================================
// Jest Setup Helpers
// =============================================================================

/**
 * Sets up common mocks for Supabase client
 */
export function mockSupabaseClient() {
  return {
    auth: {
      getSession: jest.fn().mockResolvedValue({ data: { session: null }, error: null }),
      signInWithOAuth: jest.fn().mockResolvedValue({ data: { url: 'http://localhost:4482/auth/callback' }, error: null }),
      signOut: jest.fn().mockResolvedValue({ error: null }),
    },
    from: jest.fn().mockReturnValue({
      select: jest.fn().mockReturnValue({
        data: null,
        error: null,
      }),
    }),
  };
}

/**
 * Sets up mock for fetch API (for health checks)
 */
export function mockFetch(healthData: Record<string, { status: number; body?: any }> = {}) {
  global.fetch = jest.fn((url: string) => {
    const slug = url.split('/').pop();
    const mock = healthData[slug || ''] || { status: 200, body: { status: 'healthy' } };

    return Promise.resolve({
      ok: mock.status >= 200 && mock.status < 300,
      status: mock.status,
      json: () => Promise.resolve(mock.body || {}),
    } as Response);
  }) as jest.Mock;
}

/**
 * Cleans up all mocks
 */
export function clearAllMocks() {
  jest.clearAllMocks();
  jest.clearAllTimers();
}

// =============================================================================
// Export all
// =============================================================================

export default {
  mockServiceHealth,
  mockServiceHealthMap,
  mockServiceEndpoint,
  mockServiceDefinition,
  mockServiceCatalog,
  renderWithAuth,
  renderWithServiceHealth,
  waitForHealthUpdate,
  advanceTimersBy,
  runAllTimers,
  mockSupabaseClient,
  mockFetch,
  clearAllMocks,
};
