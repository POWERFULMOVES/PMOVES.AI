/* ═══════════════════════════════════════════════════════════════════════════
   API: Graphiti Trails
   Returns CHIT-signed Graphiti trail entries from the trail log file
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import { ownerFromJwt } from '@/lib/jwtUtils';
import { logError } from '@/lib/errorUtils';
import type { GraphitiTrailsResponse, TrailEntry, TrailStats } from '@/lib/types/graphiti';

export const runtime = 'nodejs'; // Needs fs access
export const dynamic = 'force-dynamic';

/**
 * Read trail log file
 */
async function readTrailLog(): Promise<unknown> {
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
 * Convert raw trail entry to TrailEntry format.
 * Note: `isSigned` means a `sig` field was present, NOT that it was cryptographically verified.
 * HMAC verification requires CHIT passphrase and is not yet implemented in the UI layer.
 */
function toTrailEntry(raw: Record<string, unknown>, idx: number): TrailEntry {
  const isSigned = !!raw.sig;

  return {
    id: `trail-${idx}-${raw.timestamp}`,
    agentId: String(raw.agent_id || 'unknown'),
    displayName: String(raw.display_name || 'Unknown Agent'),
    glyph: String(raw.glyph || ''),
    color: String(raw.color || '#888'),
    accent: raw.accent ? String(raw.accent) : undefined,
    voice: String(raw.voice || ''),
    phase: String(raw.phase || ''),
    timestamp: String(raw.timestamp || new Date().toISOString()),
    resonance: Array.isArray(raw.resonance) ? (raw.resonance as string[]) : [],
    summary: String(raw.summary || ''),
    isVerified: isSigned,
    // Security: signatureValid is undefined until real HMAC verification is implemented
    signatureValid: undefined,
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
  const { ownerId, error: authError } = ownerFromJwt('graphiti/trails');
  if (!ownerId) {
    return NextResponse.json({ items: [], error: authError || 'Authentication required' }, { status: 401 });
  }

  const searchParams = request.nextUrl.searchParams;
  const agentIdFilter = searchParams.get('agentId');
  const phaseFilter = searchParams.get('phase');
  const resonanceFilter = searchParams.get('resonance');
  const searchQuery = searchParams.get('search')?.toLowerCase();
  const verifiedOnly = searchParams.get('verifiedOnly') === 'true';
  const limitParam = searchParams.get('limit');
  const limitParsed = parseInt(limitParam || '50', 10);
  const limit = isNaN(limitParsed) ? 50 : Math.min(limitParsed, 200);

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
    logError('Failed to load trail entries', error, 'error', {
      component: 'graphiti/trails',
    });
    return NextResponse.json(
      {
        error: 'Failed to load trail entries',
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
