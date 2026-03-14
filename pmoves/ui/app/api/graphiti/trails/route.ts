/* ═══════════════════════════════════════════════════════════════════════════
   API: Graphiti Trails
   Returns CHIT-signed Graphiti trail entries from the trail log file
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import type { GraphitiTrailsResponse, TrailEntry, TrailStats } from '@/lib/types/graphiti';

export const runtime = 'nodejs'; // Needs fs access
export const dynamic = 'force-dynamic';

/**
 * Read trail log file
 */
async function readTrailLog(): Promise<any | null> {
  try {
    const fs = await import('fs/promises');
    const path = await import('path');

    const possiblePaths = [
      path.join(process.cwd(), 'pmoves', 'docs', 'logs', 'graphiti_signed_latest.json'),
      path.join(process.cwd(), '..', '..', 'pmoves', 'docs', 'logs', 'graphiti_signed_latest.json'),
    ];

    for (const logPath of possiblePaths) {
      try {
        const content = await fs.readFile(logPath, 'utf-8');
        return JSON.parse(content);
      } catch {
        continue;
      }
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Load CHIT passphrase for verification (unused, reserved for future implementation)
 */
async function _getCHITPassphrase(): Promise<string | null> {
  try {
    // In production, this would come from a secure environment variable
    // For now, we'll check if the file exists but return null (unsigned trails)
    const fs = await import('fs/promises');
    const path = await import('path');

    const envPath = path.join(process.cwd(), 'pmoves', 'env.tier-agent');
    try {
      await fs.access(envPath);
      // Passphrase exists but we don't read it directly for security
      // Verification would happen server-side
      return 'exists';
    } catch {
      return null;
    }
  } catch {
    return null;
  }
}

/**
 * Convert raw trail entry to TrailEntry format
 */
function toTrailEntry(raw: any, idx: number): TrailEntry {
  const isVerified = !!raw.sig;

  return {
    id: `trail-${idx}-${raw.timestamp}`,
    agentId: raw.agent_id,
    displayName: raw.display_name,
    glyph: raw.glyph,
    color: raw.color,
    accent: raw.accent,
    voice: raw.voice,
    phase: raw.phase,
    timestamp: raw.timestamp,
    resonance: raw.resonance || [],
    summary: raw.summary,
    isVerified,
    signatureValid: isVerified ? true : undefined,
  };
}

/**
 * Calculate trail statistics
 */
function calculateStats(entries: TrailEntry[]): TrailStats {
  const total = entries.length;
  const verified = entries.filter((e) => e.isVerified).length;

  const byAgent: Record<string, number> = {};
  const byPhase: Record<string, number> = {};
  const byResonance: Record<string, number> = {};

  const timestamps: string[] = [];

  for (const entry of entries) {
    // By agent
    byAgent[entry.agentId] = (byAgent[entry.agentId] || 0) + 1;

    // By phase
    byPhase[entry.phase] = (byPhase[entry.phase] || 0) + 1;

    // By resonance
    for (const resonance of entry.resonance) {
      byResonance[resonance] = (byResonance[resonance] || 0) + 1;
    }

    // Track timestamps
    timestamps.push(entry.timestamp);
  }

  return {
    total,
    verified,
    unsigned: total - verified,
    byAgent,
    byPhase,
    byResonance,
    latestTimestamp: timestamps.length > 0 ? timestamps[0] : new Date().toISOString(),
    oldestTimestamp: timestamps.length > 0 ? timestamps[timestamps.length - 1] : new Date().toISOString(),
  };
}

/**
 * GET /api/graphiti/trails
 *
 * Query params:
 *   - agentId: Filter by agent ID
 *   - phase: Filter by phase
 *   - resonance: Filter by resonance domain
 *   - search: Search in summary
 *   - verifiedOnly: Return only verified entries
 *   - limit: Max results (default: 50)
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const agentIdFilter = searchParams.get('agentId');
  const phaseFilter = searchParams.get('phase');
  const resonanceFilter = searchParams.get('resonance');
  const searchQuery = searchParams.get('search')?.toLowerCase();
  const verifiedOnly = searchParams.get('verifiedOnly') === 'true';
  const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);

  try {
    const trailData = await readTrailLog();

    if (!trailData) {
      return NextResponse.json(
        {
          error: 'Trail log not found',
          items: [],
          stats: {
            total: 0,
            verified: 0,
            unsigned: 0,
            byAgent: {},
            byPhase: {},
            byResonance: {},
            latestTimestamp: new Date().toISOString(),
            oldestTimestamp: new Date().toISOString(),
          },
          timestamp: new Date().toISOString(),
        },
        { status: 404 }
      );
    }

    // Handle both single entry and array formats
    const entries = Array.isArray(trailData) ? trailData : [trailData];

    // Convert to TrailEntry format
    let trailEntries: TrailEntry[] = entries
      .map((raw, idx) => toTrailEntry(raw, idx))
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    // Apply filters
    if (agentIdFilter) {
      trailEntries = trailEntries.filter((e) => e.agentId === agentIdFilter);
    }

    if (phaseFilter) {
      trailEntries = trailEntries.filter((e) => e.phase === phaseFilter);
    }

    if (resonanceFilter) {
      trailEntries = trailEntries.filter((e) =>
        e.resonance.includes(resonanceFilter)
      );
    }

    if (searchQuery) {
      trailEntries = trailEntries.filter((e) =>
        e.summary.toLowerCase().includes(searchQuery) ||
        e.displayName.toLowerCase().includes(searchQuery)
      );
    }

    if (verifiedOnly) {
      trailEntries = trailEntries.filter((e) => e.isVerified);
    }

    // Apply limit
    trailEntries = trailEntries.slice(0, limit);

    // Calculate stats
    const stats = calculateStats(trailEntries);

    const response: GraphitiTrailsResponse = {
      items: trailEntries,
      stats,
      timestamp: new Date().toISOString(),
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120',
      },
    });

  } catch (error) {
    return NextResponse.json(
      {
        error: 'Failed to load trail entries',
        message: error instanceof Error ? error.message : String(error),
        items: [],
        stats: {
          total: 0,
          verified: 0,
          unsigned: 0,
          byAgent: {},
          byPhase: {},
          byResonance: {},
          latestTimestamp: new Date().toISOString(),
          oldestTimestamp: new Date().toISOString(),
        },
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}
