/* ═══════════════════════════════════════════════════════════════════════════
   Agent Taxonomy Types
   TypeScript types for PMOVES agent classification system
   Based on: pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Agent class hierarchy (prefix-based naming)
 */
export type AgentClass = 'Legendary' | 'Standard' | 'Specialized' | 'Utility';

/**
 * Agent type derived from 7 service tiers
 */
export type AgentType =
  | 'Data'      // Tier 1 - Earth - Brown
  | 'API'       // Tier 2 - Water - Blue
  | 'LLM'       // Tier 3 - Fire - Red
  | 'Worker'    // Tier 4 - Electric - Yellow
  | 'Media'     // Tier 5 - Wind - Cyan
  | 'Agent'     // Tier 6 - Psychic - Purple
  | 'UI';       // Tier 7 - Light - White

/**
 * Evolution stage of an agent
 */
export type EvolutionStage = 'Base' | 'Stage 1' | 'Stage 2' | 'Mega Evolution';

/**
 * Layer coverage (L0-L5)
 */
export type AgentLayer = 'L0' | 'L1' | 'L2' | 'L2.5' | 'L3' | 'L4' | 'L5';

/**
 * Agent signature from agent_signatures.yaml
 */
export interface AgentSignature {
  agent_id: string;
  display_name: string;
  glyph: string;
  color: string;
  accent?: string;
  voice: string;
  co_author?: string;
  resonance: string[];
  description?: string;
}

/**
 * Full agent definition from taxonomy
 */
export interface Agent {
  slug: string;
  name: string;
  class: AgentClass;
  primaryType: AgentType;
  secondaryType?: AgentType;
  tier: number;
  layers: AgentLayer[];
  evolutionStage: EvolutionStage;
  ports: string[];
  healthCheck?: string;
  capabilities: string[];
  dependencies?: string[];
  natsSubjects?: {
    publishes?: string[];
    subscribes?: string[];
  };
  chitToggles?: {
    delta_sensitive?: boolean;
    kappa_sensitive?: boolean;
    hz_sensitive?: boolean;
    swarm_participant?: boolean;
    attribution_gated?: boolean;
  };
  signature?: AgentSignature;
}

/**
 * Agent tree node for hierarchical visualization
 */
export interface AgentTreeNode {
  agent: Agent;
  children?: AgentTreeNode[];
  depth: number;
}

/**
 * Agent filter options
 */
export interface AgentFilterOptions {
  class?: AgentClass[];
  type?: AgentType[];
  tier?: number[];
  stage?: EvolutionStage[];
  search?: string;
  hasHealthCheck?: boolean;
}

/**
 * Agent type color mapping
 */
export const AGENT_TYPE_COLORS: Record<AgentType, { color: string; element: string }> = {
  Data: { color: '#8B4513', element: 'Earth' },
  API: { color: '#3B82F6', element: 'Water' },
  LLM: { color: '#DC2626', element: 'Fire' },
  Worker: { color: '#EAB308', element: 'Electric' },
  Media: { color: '#06B6D4', element: 'Wind' },
  Agent: { color: '#8B5CF6', element: 'Psychic' },
  UI: { color: '#F8FAFC', element: 'Light' },
};

/**
 * Agent class prefix mapping
 */
export const AGENT_CLASS_PREFIXES: Record<AgentClass, string> = {
  Legendary: 'POWERFULMOVES',
  Standard: 'PMOVES-',
  Specialized: 'Pmoves-',
  Utility: 'pmoves-',
};

/**
 * Agent taxonomy response from API
 */
export interface AgentTaxonomyResponse {
  agents: Agent[];
  byClass: Record<AgentClass, Agent[]>;
  byType: Record<AgentType, Agent[]>;
  byStage: Record<EvolutionStage, Agent[]>;
  total: number;
  timestamp: string;
}

/**
 * Agent summary statistics
 */
export interface AgentStats {
  total: number;
  byClass: Record<AgentClass, number>;
  byType: Record<AgentType, number>;
  byStage: Record<EvolutionStage, number>;
  healthyCount: number;
  totalHealthChecks: number;
}
