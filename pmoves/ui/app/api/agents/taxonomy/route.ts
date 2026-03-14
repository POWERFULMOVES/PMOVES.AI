/* ═══════════════════════════════════════════════════════════════════════════
   API: Agent Taxonomy
   Returns PMOVES agent classification data from taxonomy markdown + signatures
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import { SERVICE_CATALOG } from '@/lib/serviceCatalog';
import type { AgentTaxonomyResponse, Agent, AgentStats } from '@/lib/types/agents';

export const runtime = 'nodejs'; // Needs fs access for reading local files
export const dynamic = 'force-dynamic';

/**
 * Parse agent type chart from taxonomy markdown
 */
function parseTypeChart(markdown: string): Map<string, { primaryType: Agent['primaryType']; secondaryType?: Agent['primaryType']; tier: number }> {
  const typeChartSection = markdown.split('### Type Chart: Agent Roster')[1]?.split('###')[0];
  if (!typeChartSection) return new Map();

  const agentTypes = new Map();
  const lines = typeChartSection.split('\n');

  // Valid agent types for validation
  const validTypes: Agent['primaryType'][] = ['Data', 'API', 'LLM', 'Worker', 'Media', 'Agent', 'UI'];

  for (const line of lines) {
    const match = line.match(/\|([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)?\s*\|\s*([^|]+)\s*\|/);
    if (match && match[1].trim() !== 'Agent') {
      const name = match[1].trim();
      const primaryTypeRaw = match[2].trim();
      const secondaryTypeRaw = match[3]?.trim();
      const tier = parseInt(match[4].trim(), 10);

      // Validate and capitalize types to match Agent['primaryType']
      const primaryType = validTypes.find(t => t.toLowerCase() === primaryTypeRaw.toLowerCase()) || 'Worker';
      const secondaryType = secondaryTypeRaw
        ? validTypes.find(t => t.toLowerCase() === secondaryTypeRaw.toLowerCase())
        : undefined;

      agentTypes.set(name, { primaryType, secondaryType, tier });
    }
  }

  return agentTypes;
}

/**
 * Parse layer coverage from taxonomy markdown
 */
function parseLayerCoverage(markdown: string): Map<string, string[]> {
  const layerSection = markdown.split('### Agent Layer Coverage Map')[1]?.split('###')[0];
  if (!layerSection) return new Map();

  const agentLayers = new Map();
  const lines = layerSection.split('\n');

  for (const line of lines) {
    const match = line.match(/([A-Z][A-Za-z-]+)\s+\*+\s+([\s\*]+)\s+(\d+)/);
    if (match) {
      const name = match[1];
      const layerStr = match[2];
      const layerCount = parseInt(match[3], 10);

      const layers: string[] = [];
      if (layerStr.includes('*')) {
        if (layerStr.includes('L0')) layers.push('L0');
        if (layerStr.includes('L1')) layers.push('L1');
        if (layerStr.includes('L2')) layers.push('L2');
        if (layerStr.includes('L2.5')) layers.push('L2.5');
        if (layerStr.includes('L3')) layers.push('L3');
        if (layerStr.includes('L4')) layers.push('L4');
        if (layerStr.includes('L5')) layers.push('L5');
      }

      agentLayers.set(name, layers);
    }
  }

  return agentLayers;
}

/**
 * Map service catalog to agent definitions
 */
function buildAgentsFromCatalog(
  typeChart: Map<string, { primaryType: Agent['primaryType']; secondaryType?: Agent['primaryType']; tier: number }>,
  layerCoverage: Map<string, string[]>,
  signatures: Record<string, any>
): Agent[] {
  const agents: Agent[] = [];

  for (const service of SERVICE_CATALOG) {
    // Determine agent class from slug prefix
    let agentClass: Agent['class'];
    if (service.slug.startsWith('POWERFULMOVES')) {
      agentClass = 'Legendary';
    } else if (service.slug.startsWith('PMOVES-')) {
      agentClass = 'Standard';
    } else if (service.slug.startsWith('Pmoves-')) {
      agentClass = 'Specialized';
    } else {
      agentClass = 'Utility';
    }

    // Get type info from parsed chart (fallback to mapped category)
    const typeInfo = typeChart.get(service.title);
    const primaryType = typeInfo?.primaryType || getCategoryAgentType(service.category);
    const secondaryType = typeInfo?.secondaryType;
    const tier = typeInfo?.tier ?? getCategoryTier(service.category);

    // Get layer coverage
    const layers = layerCoverage.get(service.title) || [];

    // Determine evolution stage from layer count
    const layerCount = layers.length;
    let evolutionStage: Agent['evolutionStage'];
    if (layerCount >= 7) {
      evolutionStage = 'Mega Evolution';
    } else if (layerCount >= 5) {
      evolutionStage = 'Stage 2';
    } else if (layerCount >= 3) {
      evolutionStage = 'Stage 1';
    } else {
      evolutionStage = 'Base';
    }

    // Get signature if available
    const slugLower = service.slug.toLowerCase().replace(/[^a-z0-9]/g, '-');
    const signature = signatures[slugLower] || signatures[service.slug];

    agents.push({
      slug: service.slug,
      name: service.title,
      class: agentClass,
      primaryType,
      secondaryType,
      tier,
      layers: layers as Agent['layers'],
      evolutionStage,
      ports: service.endpoints.map((e) => e.port),
      healthCheck: service.healthCheck,
      capabilities: service.capabilities || [],
      dependencies: service.dependencies,
      signature: signature ? {
        agent_id: signature.agent_id || slugLower,
        display_name: signature.display_name || service.title,
        glyph: signature.glyph || '◆',
        color: signature.color || '#7C3AED',
        accent: signature.accent,
        voice: signature.voice || 'analytical',
        co_author: signature.co_author,
        resonance: signature.resonance || [],
        description: signature.description,
      } : undefined,
    });
  }

  return agents;
}

/**
 * Map service category to valid AgentType
 */
function getCategoryAgentType(category: string): Agent['primaryType'] {
  const typeMap: Record<string, Agent['primaryType']> = {
    data: 'Data',
    database: 'Data',
    bus: 'API',
    api: 'API',
    llm: 'LLM',
    workers: 'Worker',
    gpu: 'Worker',
    media: 'Media',
    agents: 'Agent',
    ui: 'UI',
    observability: 'Data',
    integration: 'API',
  };
  return typeMap[category] || 'Worker'; // Default to Worker for unknown categories
}

/**
 * Map service category to tier number
 */
function getCategoryTier(category: string): number {
  const tierMap: Record<string, number> = {
    data: 1,
    database: 1,
    bus: 1,
    api: 2,
    llm: 3,
    workers: 4,
    gpu: 4,
    media: 5,
    agents: 6,
    ui: 7,
    observability: 1,
    integration: 2,
  };
  return tierMap[category] || 4;
}

/**
 * Load agent signatures from YAML
 */
async function loadSignatures(): Promise<Record<string, any>> {
  try {
    const fs = await import('fs/promises');
    const path = await import('path');

    // Try both absolute and relative paths
    const possiblePaths = [
      path.join(process.cwd(), 'pmoves', 'config', 'agent_signatures.yaml'),
      path.join(process.cwd(), '..', '..', 'pmoves', 'config', 'agent_signatures.yaml'),
    ];

    for (const yamlPath of possiblePaths) {
      try {
        const content = await fs.readFile(yamlPath, 'utf-8');
        // Simple YAML parser for our structure
        const signatures: Record<string, any> = {};
        let currentSection: string | null = null;

        for (const line of content.split('\n')) {
          const indentMatch = line.match(/^(\s*)-/);
          if (!indentMatch) continue;

          const indent = indentMatch[1].length;

          if (indent === 0) {
            const keyMatch = line.match(/\s*(\w+):/);
            if (keyMatch) {
              currentSection = keyMatch[1];
              signatures[currentSection] = {};
            }
          } else if (currentSection && indent === 2) {
            const kvMatch = line.match(/\s*(\w+):\s*(.+)/);
            if (kvMatch) {
              const key = kvMatch[1];
              let value: string | string[] | boolean = kvMatch[2].trim();

              // Handle array values
              if (typeof value === 'string' && value.startsWith('[')) {
                value = value
                  .slice(1, -1)
                  .split(',')
                  .map((v) => v.trim().replace(/['"]/g, ''));
              } else if (value === 'true' || value === 'false') {
                value = value === 'true';
              }

              signatures[currentSection][key] = value;
            }
          }
        }

        return signatures;
      } catch {
        // Try next path
        continue;
      }
    }

    return {};
  } catch {
    return {};
  }
}

/**
 * Load taxonomy markdown
 */
async function loadTaxonomyMarkdown(): Promise<string> {
  try {
    const fs = await import('fs/promises');
    const path = await import('path');

    const possiblePaths = [
      path.join(process.cwd(), 'pmoves', 'docs', 'AGENTS', 'PMOVES_AGENT_CLASS_TAXONOMY.md'),
      path.join(process.cwd(), '..', '..', 'pmoves', 'docs', 'AGENTS', 'PMOVES_AGENT_CLASS_TAXONOMY.md'),
    ];

    for (const markdownPath of possiblePaths) {
      try {
        return await fs.readFile(markdownPath, 'utf-8');
      } catch {
        continue;
      }
    }

    return '';
  } catch {
    return '';
  }
}

/**
 * GET /api/agents/taxonomy
 *
 * Query params:
 *   - class: Filter by agent class (Legendary, Standard, Specialized, Utility)
 *   - type: Filter by agent type (Data, API, LLM, Worker, Media, Agent, UI)
 *   - search: Search by name
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const classParam = searchParams.get('class');
  const typeParam = searchParams.get('type');
  const searchQuery = searchParams.get('search')?.toLowerCase();

  // Type-safe filter parsing
  const validClasses: Agent['class'][] = ['Legendary', 'Standard', 'Specialized', 'Utility'];
  const validTypes: Agent['primaryType'][] = ['Data', 'API', 'LLM', 'Worker', 'Media', 'Agent', 'UI'];

  const classFilter = classParam
    ? classParam.split(',').filter((c): c is Agent['class'] => validClasses.includes(c as Agent['class']))
    : undefined;

  const typeFilter = typeParam
    ? typeParam.split(',').filter((t): t is Agent['primaryType'] => validTypes.includes(t as Agent['primaryType']))
    : undefined;

  try {
    // Load taxonomy data
    const [markdown, signatures] = await Promise.all([
      loadTaxonomyMarkdown(),
      loadSignatures(),
    ]);

    if (!markdown) {
      return NextResponse.json(
        { error: 'Taxonomy markdown not found' },
        { status: 404 }
      );
    }

    // Parse markdown
    const typeChart = parseTypeChart(markdown);
    const layerCoverage = parseLayerCoverage(markdown);

    // Build agents from service catalog
    let agents = buildAgentsFromCatalog(typeChart, layerCoverage, signatures);

    // Apply filters
    if (classFilter) {
      agents = agents.filter((a) => classFilter.includes(a.class));
    }
    if (typeFilter) {
      agents = agents.filter((a) =>
        typeFilter.includes(a.primaryType) || typeFilter.includes(a.secondaryType!)
      );
    }
    if (searchQuery) {
      agents = agents.filter((a) =>
        a.name.toLowerCase().includes(searchQuery) ||
        a.slug.toLowerCase().includes(searchQuery)
      );
    }

    // Group by class
    const byClass: Record<Agent['class'], Agent[]> = {
      Legendary: agents.filter((a) => a.class === 'Legendary'),
      Standard: agents.filter((a) => a.class === 'Standard'),
      Specialized: agents.filter((a) => a.class === 'Specialized'),
      Utility: agents.filter((a) => a.class === 'Utility'),
    };

    // Group by type
    const byType: Record<Agent['primaryType'], Agent[]> = {
      Data: agents.filter((a) => a.primaryType === 'Data'),
      API: agents.filter((a) => a.primaryType === 'API'),
      LLM: agents.filter((a) => a.primaryType === 'LLM'),
      Worker: agents.filter((a) => a.primaryType === 'Worker'),
      Media: agents.filter((a) => a.primaryType === 'Media'),
      Agent: agents.filter((a) => a.primaryType === 'Agent'),
      UI: agents.filter((a) => a.primaryType === 'UI'),
    };

    // Group by stage
    const byStage: Record<Agent['evolutionStage'], Agent[]> = {
      Base: agents.filter((a) => a.evolutionStage === 'Base'),
      'Stage 1': agents.filter((a) => a.evolutionStage === 'Stage 1'),
      'Stage 2': agents.filter((a) => a.evolutionStage === 'Stage 2'),
      'Mega Evolution': agents.filter((a) => a.evolutionStage === 'Mega Evolution'),
    };

    const response: AgentTaxonomyResponse = {
      agents,
      byClass,
      byType,
      byStage,
      total: agents.length,
      timestamp: new Date().toISOString(),
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    });

  } catch (error) {
    return NextResponse.json(
      {
        error: 'Failed to load agent taxonomy',
        message: error instanceof Error ? error.message : String(error),
        agents: [],
        byClass: { Legendary: [], Standard: [], Specialized: [], Utility: [] },
        byType: { Data: [], API: [], LLM: [], Worker: [], Media: [], Agent: [], UI: [] },
        byStage: { Base: [], 'Stage 1': [], 'Stage 2': [], 'Mega Evolution': [] },
        total: 0,
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}
