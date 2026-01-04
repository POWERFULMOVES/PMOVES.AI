import { NextResponse } from 'next/server';

/**
 * Health check endpoint for container orchestration.
 * Returns service status, name, and timestamp.
 */
export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'pmoves-ui',
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version || '0.1.0',
  });
}
