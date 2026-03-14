import { NextResponse } from 'next/server';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';

/**
 * Health check endpoint for container orchestration.
 * Returns service status, database connectivity, and timestamp.
 *
 * Checks Supabase database connectivity to ensure service health
 * reflects actual availability of dependencies.
 */
export async function GET() {
  let dbStatus: 'healthy' | 'unhealthy' | 'unknown' = 'unknown';
  let dbError: string | undefined;

  // Check Supabase database connectivity
  try {
    const supabase = getServiceSupabaseClient();
    const { error } = await supabase
      .from('upload_events')
      .select('id')
      .limit(1);

    if (error) {
      dbStatus = 'unhealthy';
      dbError = error.message;
    } else {
      dbStatus = 'healthy';
    }
  } catch (err) {
    dbStatus = 'unhealthy';
    dbError = err instanceof Error ? err.message : 'Unknown DB error';
  }

  // Overall service status is degraded if database is unhealthy
  const overallStatus = dbStatus === 'healthy' ? 'healthy' : 'degraded';
  const httpStatus = overallStatus === 'healthy' ? 200 : 503;

  return NextResponse.json({
    status: overallStatus,
    service: 'pmoves-ui',
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version || '0.1.0',
    checks: {
      database: {
        status: dbStatus,
        error: dbError,
      },
    },
  }, { status: httpStatus });
}
