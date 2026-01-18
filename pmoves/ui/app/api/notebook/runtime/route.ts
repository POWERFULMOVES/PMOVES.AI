import { NextRequest, NextResponse } from 'next/server';
import { logError } from '@/lib/errorUtils';
import { ErrorIds } from '@/lib/constants/errorIds';

// Notebook Sync service endpoint
const NOTEBOOK_SYNC_URL = (
  process.env.NOTEBOOK_SYNC_URL ||
  process.env.NEXT_PUBLIC_NOTEBOOK_SYNC_URL ||
  'http://localhost:8095'
).replace(/\/$/, '');

export async function GET(_req: NextRequest) {
  const healthUrl = `${NOTEBOOK_SYNC_URL}/healthz`;
  const metricsUrl = `${NOTEBOOK_SYNC_URL}/metrics`;

  try {
    // Fetch health status
    const healthRes = await fetch(healthUrl, {
      cache: 'no-store',
      signal: AbortSignal.timeout(5000), // 5 second timeout
    });

    const health = await healthRes.json().catch(() => ({ status: 'unknown' }));

    // Fetch Prometheus metrics
    const metricsRes = await fetch(metricsUrl, {
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    });

    let metrics: Record<string, number | string> | null = null;
    if (metricsRes.ok) {
      const metricsText = await metricsRes.text();
      // Parse Prometheus metrics format
      metrics = parsePrometheusMetrics(metricsText);
    }

    return NextResponse.json({
      service: 'notebook-sync',
      endpoint: NOTEBOOK_SYNC_URL,
      health: health.status || 'unknown',
      metrics,
    });
  } catch (err) {
    logError('Failed to fetch notebook-sync runtime status', err instanceof Error ? err : new Error(String(err)), 'error', {
      errorId: ErrorIds.NOTEBOOK_RUNTIME_FETCH_FAILED,
      component: 'notebook-runtime-api',
      endpoint: NOTEBOOK_SYNC_URL,
    });
    return NextResponse.json(
      { service: 'notebook-sync', endpoint: NOTEBOOK_SYNC_URL, health: 'error', metrics: null, error: 'Service unavailable' },
      { status: 503 }
    );
  }
}

/**
 * Parse Prometheus metrics text format into key-value pairs
 */
function parsePrometheusMetrics(metricsText: string): Record<string, number | string> {
  const result: Record<string, number | string> = {};
  const lines = metricsText.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    // Skip comments and empty lines
    if (!trimmed || trimmed.startsWith('#')) continue;

    // Parse metric lines (NAME value)
    const match = trimmed.match(/^(\w+(?:\{[^}]*\})?)\s+(\S+)/);
    if (match) {
      const name = match[1].replace(/\{.*\}/, ''); // Remove labels
      const value = parseFloat(match[2]);
      if (!isNaN(value)) {
        result[name] = value;
      }
    }
  }

  return result;
}
