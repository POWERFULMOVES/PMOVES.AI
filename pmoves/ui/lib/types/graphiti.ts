/* ═══════════════════════════════════════════════════════════════════════════
   Graphiti Trail Types
   TypeScript types for CHIT-signed Graphiti trail entries
   Based on: pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Graphiti signature metadata
 */
export interface GraphitiSignature {
  alg: string;
  kid: string;
  hmac?: string;
}

/**
 * CHIT-signed Graphiti trail entry
 */
export interface GraphitiTrailEntry {
  agent_id: string;
  display_name: string;
  glyph: string;
  color: string;
  accent?: string;
  voice: string;
  phase: string;
  timestamp: string;
  resonance: string[];
  summary: string;
  sig?: GraphitiSignature;
}

/**
 * Trail entry for UI display
 */
export interface TrailEntry {
  id: string;
  agentId: string;
  displayName: string;
  glyph: string;
  color: string;
  accent?: string;
  voice: string;
  phase: string;
  timestamp: string;
  resonance: string[];
  summary: string;
  isVerified: boolean;
  signatureValid?: boolean;
}

/**
 * Trail filter options
 */
export interface TrailFilterOptions {
  agentId?: string;
  phase?: string;
  resonance?: string[];
  search?: string;
  verifiedOnly?: boolean;
  limit?: number;
}

/**
 * Trail sort options
 */
export type TrailSortField = 'timestamp' | 'agent' | 'phase';
export type TrailSortDirection = 'asc' | 'desc';

/**
 * Trail statistics
 */
export interface TrailStats {
  total: number;
  verified: number;
  unsigned: number;
  byAgent: Record<string, number>;
  byPhase: Record<string, number>;
  byResonance: Record<string, number>;
  latestTimestamp: string;
  oldestTimestamp: string;
}

/**
 * Graphiti trails API response
 */
export interface GraphitiTrailsResponse {
  items: TrailEntry[];
  stats: TrailStats;
  timestamp: string;
}

/**
 * CHIT verification result
 */
export interface CHITVerificationResult {
  isValid: boolean;
  signaturePresent: boolean;
  algorithm?: string;
  keyId?: string;
  error?: string;
}
