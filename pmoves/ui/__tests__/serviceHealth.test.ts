/* ═══════════════════════════════════════════════════════════════════════════
   Tests: serviceHealth.ts — timeout clamping, probes, and utilities
   ═══════════════════════════════════════════════════════════════════════════ */

import type { ServiceDefinition } from '../lib/serviceCatalog';

// Minimal mock catalog — override per test as needed
const MOCK_SERVICE: ServiceDefinition = {
  slug: 'test-svc',
  title: 'Test Service',
  summary: 'A mock service',
  category: 'agents',
  color: 'cyan',
  endpoints: [],
  healthCheck: 'http://localhost:9999/healthz',
};

const MOCK_SERVICE_NO_HEALTH: ServiceDefinition = {
  slug: 'no-health',
  title: 'No Health',
  summary: 'Service without health check',
  category: 'agents',
  color: 'cyan',
  endpoints: [],
};

// ── Mock SERVICE_CATALOG so checkAllServices iterates our fixtures ────────
jest.mock('../lib/serviceCatalog', () => ({
  SERVICE_CATALOG: [
    {
      slug: 'svc-a',
      title: 'A',
      summary: '',
      category: 'database',
      color: 'cyan',
      endpoints: [],
      healthCheck: 'http://localhost:1111/healthz',
    },
    {
      slug: 'svc-b',
      title: 'B',
      summary: '',
      category: 'agents',
      color: 'cyan',
      endpoints: [],
      healthCheck: 'http://localhost:2222/healthz',
    },
    {
      slug: 'svc-c',
      title: 'C',
      summary: '',
      category: 'database',
      color: 'cyan',
      endpoints: [],
      // no healthCheck → unknown
    },
  ],
}));

// ── Imports (after mock registration) ────────────────────────────────────
import {
  probeService,
  checkAllServices,
  getHealthPercentage,
  formatResponseTime,
  getStatusText,
  createHealthMap,
} from '../lib/serviceHealth';

// ── Helpers ──────────────────────────────────────────────────────────────

/** Capture the `ms` value passed to setTimeout */
function captureSetTimeoutMs(): { get: () => number } {
  const holder = { value: 0 };
  const orig = global.setTimeout;
  jest.spyOn(global, 'setTimeout').mockImplementation((fn: TimerHandler, ms?: number) => {
    holder.value = ms ?? 0;
    return orig(fn, 0); // execute immediately for test speed
  });
  return { get: () => holder.value };
}

beforeEach(() => {
  jest.restoreAllMocks();
  delete (process.env as Record<string, string | undefined>).HEALTH_CHECK_HOST;
});

// ═══════════════════════════════════════════════════════════════════════════
// probeService — timeout clamping
// ═══════════════════════════════════════════════════════════════════════════

describe('probeService — timeout clamping', () => {
  // Stub fetch so probe completes without network
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
  });

  it.each([
    ['default (5000)', 5000, 5000],
    ['below MIN (500)', 500, 1000],
    ['above MAX (120000)', 120_000, 60_000],
    ['exact MIN (1000)', 1000, 1000],
    ['exact MAX (60000)', 60_000, 60_000],
    ['negative (-1)', -1, 1000],
  ])('clamps %s → %i ms', async (_label, input, expected) => {
    const ms = captureSetTimeoutMs();
    await probeService(MOCK_SERVICE, input);
    expect(ms.get()).toBe(expected);
  });

  it('clamps NaN to MIN_TIMEOUT (1000)', async () => {
    const ms = captureSetTimeoutMs();
    await probeService(MOCK_SERVICE, NaN);
    expect(ms.get()).toBe(1000);
  });

  it('clamps Infinity to MIN_TIMEOUT (1000)', async () => {
    const ms = captureSetTimeoutMs();
    await probeService(MOCK_SERVICE, Infinity);
    expect(ms.get()).toBe(1000);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// probeService — health check behavior
// ═══════════════════════════════════════════════════════════════════════════

describe('probeService — health check behavior', () => {
  it('returns unknown when service has no healthCheck URL', async () => {
    const result = await probeService(MOCK_SERVICE_NO_HEALTH);
    expect(result.status).toBe('unknown');
    expect(result.slug).toBe('no-health');
    expect(result.responseTime).toBeUndefined();
  });

  it('returns healthy when fetch responds ok', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
    const result = await probeService(MOCK_SERVICE);
    expect(result.status).toBe('healthy');
    expect(result.responseTime).toBeDefined();
    expect(result.error).toBeUndefined();
  });

  it('returns unhealthy with HTTP status on non-ok response', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 503 });
    const result = await probeService(MOCK_SERVICE);
    expect(result.status).toBe('unhealthy');
    expect(result.error).toBe('HTTP 503');
  });

  it('returns unhealthy on network error', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'));
    const result = await probeService(MOCK_SERVICE);
    expect(result.status).toBe('unhealthy');
    expect(result.error).toBe('ECONNREFUSED');
  });

  it('returns unhealthy on abort (timeout)', async () => {
    const abortError = new DOMException('The operation was aborted', 'AbortError');
    global.fetch = jest.fn().mockRejectedValue(abortError);
    const result = await probeService(MOCK_SERVICE);
    expect(result.status).toBe('unhealthy');
    expect(result.error).toContain('aborted');
  });

  it('calls clearTimeout in finally block', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
    const clearSpy = jest.spyOn(global, 'clearTimeout');
    await probeService(MOCK_SERVICE);
    expect(clearSpy).toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// probeService — resolveHealthUrl (HEALTH_CHECK_HOST)
// ═══════════════════════════════════════════════════════════════════════════

describe('probeService — resolveHealthUrl', () => {
  it('leaves URL unchanged when HEALTH_CHECK_HOST is unset', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
    await probeService(MOCK_SERVICE);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:9999/healthz',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('rewrites localhost when HEALTH_CHECK_HOST is set', async () => {
    // HEALTH_HOST is captured at module level, so we must re-import the
    // module after setting the env var to exercise the rewrite path.
    process.env.HEALTH_CHECK_HOST = 'host.docker.internal';
    jest.resetModules();
    const { probeService: freshProbe } = await import('../lib/serviceHealth');

    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
    await freshProbe(MOCK_SERVICE);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://host.docker.internal:9999/healthz',
      expect.objectContaining({ method: 'GET' })
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// checkAllServices — orchestration
// ═══════════════════════════════════════════════════════════════════════════

describe('checkAllServices', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
  });

  it('returns all services from catalog', async () => {
    const result = await checkAllServices();
    expect(result.services).toHaveLength(3);
    expect(result.total).toBe(3);
  });

  it('filters by category', async () => {
    const result = await checkAllServices(5000, { category: 'database' });
    expect(result.services).toHaveLength(2);
    expect(result.services.every((s) => ['svc-a', 'svc-c'].includes(s.slug))).toBe(true);
  });

  it('filters by slugs', async () => {
    const result = await checkAllServices(5000, { slugs: ['svc-b'] });
    expect(result.services).toHaveLength(1);
    expect(result.services[0].slug).toBe('svc-b');
  });

  it('calculates statistics correctly (healthy + unknown mix)', async () => {
    // svc-a and svc-b have healthCheck → healthy (fetch mocked ok)
    // svc-c has no healthCheck → unknown
    const result = await checkAllServices();
    expect(result.healthy).toBe(2);
    expect(result.unknown).toBe(1);
    expect(result.unhealthy).toBe(0);
  });

  it('passes timeout to probeService', async () => {
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout');
    await checkAllServices(3000);
    // setTimeout called for each service with healthCheck (svc-a, svc-b)
    const timeoutCalls = setTimeoutSpy.mock.calls.filter(
      ([, ms]) => typeof ms === 'number' && ms === 3000
    );
    expect(timeoutCalls.length).toBe(2);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Utility functions (pure, no mocks)
// ═══════════════════════════════════════════════════════════════════════════

describe('getHealthPercentage', () => {
  it('returns correct percentage', () => {
    expect(getHealthPercentage({ total: 10, healthy: 7, unhealthy: 2, unknown: 1, services: [], timestamp: new Date() })).toBe(70);
  });

  it('returns 0 when total is 0', () => {
    expect(getHealthPercentage({ total: 0, healthy: 0, unhealthy: 0, unknown: 0, services: [], timestamp: new Date() })).toBe(0);
  });
});

describe('formatResponseTime', () => {
  it('returns -- for undefined', () => {
    expect(formatResponseTime(undefined)).toBe('--');
  });

  it('returns ms for values under 1000', () => {
    expect(formatResponseTime(500)).toBe('500ms');
  });

  it('returns seconds for values >= 1000', () => {
    expect(formatResponseTime(1500)).toBe('1.5s');
  });
});

describe('getStatusText', () => {
  it.each([
    ['healthy', 'Online'],
    ['unhealthy', 'Offline'],
    ['checking', 'Checking...'],
    ['unknown', 'Unknown'],
  ] as const)('maps %s → %s', (status, expected) => {
    expect(getStatusText(status)).toBe(expected);
  });
});

describe('createHealthMap', () => {
  it('builds indexable map from result', () => {
    const result = {
      services: [
        { slug: 'a', status: 'healthy' as const, responseTime: 42, lastCheck: new Date() },
        { slug: 'b', status: 'unhealthy' as const, responseTime: 100, lastCheck: new Date(), error: 'fail' },
      ],
      timestamp: new Date(),
      total: 2,
      healthy: 1,
      unhealthy: 1,
      unknown: 0,
    };

    const map = createHealthMap(result);
    expect(map['a']).toEqual({ status: 'healthy', responseTime: 42 });
    expect(map['b']).toEqual({ status: 'unhealthy', responseTime: 100 });
  });
});
