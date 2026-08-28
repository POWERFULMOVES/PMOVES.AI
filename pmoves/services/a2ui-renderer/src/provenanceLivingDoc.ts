export interface ProvenanceTerm {
  term: string;
  weight?: number;
  cluster?: string;
  role?: string;
}

export interface ProvenanceSection {
  heading: string;
  body: string;
}

export interface ProvenanceReference {
  label: string;
  uri?: string;
  kind?: string;
}

export interface ProvenancePalette {
  background: string;
  panel: string;
  panelAlt: string;
  accent: string;
  accentSoft: string;
  ink: string;
  muted: string;
}

export interface ProvenanceLivingDoc {
  title: string;
  subtitle: string;
  summary: string;
  merkle_root: string;
  shape_id: string;
  favorite_words: string[];
  weighted_terms: ProvenanceTerm[];
  sections: ProvenanceSection[];
  provenance_refs: ProvenanceReference[];
  duration_ms: number;
  palette: ProvenancePalette;
}

export interface ProvenanceLivingDocSummary {
  section_count: number;
  weighted_term_count: number;
  favorite_word_count: number;
  provenance_ref_count: number;
  merkle_root_present: boolean;
  shape_id_present: boolean;
}

// DL-2: palettes sourced from the PMOVES design token engine
// (pmoves/design/build/tokens.{pmoves-armor,darkxside-skin}.css, generated from
// pmoves/config/agent_signatures.yaml). Kept as literals here because this
// renderer is a separate bundle; values mirror the generated tokens 1:1. If the
// tokens change, update these to match (one source of truth = the registry).

// Canonical PMOVES "armor" (cool): void bg, violet accent (claude-opus),
// teal secondary (4090). Default for generic provenance docs.
export const ARMOR_PALETTE: ProvenancePalette = {
  background: '#050508',               // --pm-void
  panel: 'rgba(18, 18, 26, 0.82)',     // --pm-surface @ .82
  panelAlt: 'rgba(10, 10, 15, 0.78)',  // --pm-void-elevated @ .78
  accent: '#7C3AED',                   // --pm-accent (claude-opus / DARKXSIDE purple)
  accentSoft: '#0D9488',               // --pm-accent-2 (teal secondary)
  ink: '#f8f8f8',                      // --pm-ink
  muted: '#a0a0a8',                    // --pm-ink-dim
};

// DARKXSIDE "skin" (warm): ✦ crimson signature lead. Pass this for
// DARKXSIDE-attributed provenance docs (the portal surface).
export const SKIN_PALETTE: ProvenancePalette = {
  background: '#0a0608',               // --pm-bg (skin)
  panel: 'rgba(18, 18, 26, 0.82)',     // --pm-surface @ .82
  panelAlt: 'rgba(20, 10, 14, 0.78)',  // --pm-bg-tint @ .78
  accent: '#E11D48',                   // --pm-accent (darkxside ✦ crimson)
  accentSoft: '#FB7185',               // --pm-accent-soft (darkxside accent)
  ink: '#f8f8f8',                      // --pm-ink
  muted: '#a0a0a8',                    // --pm-ink-dim
};

const DEFAULT_PALETTE: ProvenancePalette = ARMOR_PALETTE;

// DL-3.3 — persona-adaptive palette patch. Gateway theme shape from
// GET /v1/agent/theme/{id}: { color, accent, glyph, ... }. Accent family only:
// background/panel/ink stay with the base palette (spec D3) so a persona can
// tint a provenance doc without inventing a whole new surface.
export interface PersonaAccentTheme {
  color?: string;
  accent?: string;
}

export function personaPalette(
  theme: PersonaAccentTheme | null | undefined,
  base: ProvenancePalette = ARMOR_PALETTE
): ProvenancePalette {
  if (!theme || typeof theme !== 'object') return { ...base };
  return {
    ...base,
    ...(theme.color ? { accent: theme.color } : {}),
    ...(theme.accent ? { accentSoft: theme.accent } : {}),
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function asString(value: unknown, fallback: string, maxLength: number): string {
  if (typeof value !== 'string') {
    return fallback;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return fallback;
  }
  return trimmed.slice(0, maxLength);
}

function asStringList(value: unknown, maxItems: number, maxLength: number): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter(Boolean)
    .slice(0, maxItems)
    .map((item) => item.slice(0, maxLength));
}

function asNumber(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function normalizeWeight(value: unknown): number {
  return clamp(asNumber(value, 0.5), 0, 1);
}

function normalizeSections(value: unknown): ProvenanceSection[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((entry) => {
      if (!entry || typeof entry !== 'object') {
        return null;
      }
      const record = entry as Record<string, unknown>;
      const heading = asString(record.heading, '', 80);
      const body = asString(record.body, '', 600);
      if (!heading && !body) {
        return null;
      }
      return {
        heading: heading || 'Section',
        body: body || heading,
      };
    })
    .filter((entry): entry is ProvenanceSection => entry !== null)
    .slice(0, 4);
}

function normalizeReferences(value: unknown): ProvenanceReference[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((entry) => {
      if (typeof entry === 'string') {
        const label = entry.trim();
        if (!label) {
          return null;
        }
        return { label: label.slice(0, 120) };
      }
      if (!entry || typeof entry !== 'object') {
        return null;
      }
      const record = entry as Record<string, unknown>;
      const label = asString(record.label, '', 120);
      const uri = asString(record.uri, '', 240);
      const kind = asString(record.kind, '', 40);
      if (!label && !uri) {
        return null;
      }
      return {
        label: label || uri,
        uri: uri || undefined,
        kind: kind || undefined,
      };
    })
    .filter((entry): entry is ProvenanceReference => entry !== null)
    .slice(0, 6);
}

function normalizeTerms(value: unknown): ProvenanceTerm[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const terms: ProvenanceTerm[] = [];
  for (const entry of value) {
    if (typeof entry === 'string') {
      const term = entry.trim();
      if (term) {
        terms.push({ term: term.slice(0, 60), weight: 0.5 });
      }
      continue;
    }
    if (!entry || typeof entry !== 'object') {
      continue;
    }
    const record = entry as Record<string, unknown>;
    const term = asString(record.term, '', 60);
    if (!term) {
      continue;
    }
    terms.push({
      term,
      weight: normalizeWeight(record.weight),
      cluster: asString(record.cluster, '', 40) || undefined,
      role: asString(record.role, '', 40) || undefined,
    });
  }
  return terms
    .sort((left, right) => (right.weight ?? 0) - (left.weight ?? 0))
    .slice(0, 8);
}

function normalizePalette(value: unknown): ProvenancePalette {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_PALETTE };
  }
  const record = value as Record<string, unknown>;
  return {
    background: asString(record.background, DEFAULT_PALETTE.background, 40),
    panel: asString(record.panel, DEFAULT_PALETTE.panel, 64),
    panelAlt: asString(record.panelAlt, DEFAULT_PALETTE.panelAlt, 64),
    accent: asString(record.accent, DEFAULT_PALETTE.accent, 40),
    accentSoft: asString(record.accentSoft, DEFAULT_PALETTE.accentSoft, 40),
    ink: asString(record.ink, DEFAULT_PALETTE.ink, 40),
    muted: asString(record.muted, DEFAULT_PALETTE.muted, 40),
  };
}

export function estimateProvenanceDurationMs(input: Record<string, unknown>): number {
  const sectionCount = Array.isArray(input.sections) ? input.sections.length : 0;
  const termCount = Array.isArray(input.weighted_terms) ? input.weighted_terms.length : 0;
  const refCount = Array.isArray(input.provenance_refs) ? input.provenance_refs.length : 0;
  const summaryLength = typeof input.summary === 'string' ? input.summary.length : 0;

  return clamp(
    9000
      + sectionCount * 1500
      + termCount * 180
      + refCount * 160
      + Math.ceil(summaryLength / 40) * 120,
    9000,
    24000,
  );
}

export function normalizeProvenanceLivingDoc(input: unknown): ProvenanceLivingDoc {
  const record = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  const title = asString(record.title, 'PMOVES Living Document', 120);
  const subtitle = asString(record.subtitle, 'Provenance surfaced as motion-ready context', 160);
  const sections = normalizeSections(record.sections);
  const weightedTerms = normalizeTerms(record.weighted_terms);
  const favoriteWords = asStringList(record.favorite_words, 8, 40);
  const provenanceRefs = normalizeReferences(record.provenance_refs);
  const summary = asString(
    record.summary,
    'Signal-routed content prepared for living-doc review and motion export.',
    800,
  );
  const durationMs = clamp(
    asNumber(record.duration_ms, estimateProvenanceDurationMs(record)),
    9000,
    24000,
  );

  return {
    title,
    subtitle,
    summary,
    merkle_root: asString(record.merkle_root, 'pending-merkle-root', 120),
    shape_id: asString(record.shape_id, 'pending-shape-id', 120),
    favorite_words: favoriteWords,
    weighted_terms: weightedTerms,
    sections: sections.length > 0 ? sections : [{
      heading: 'Context',
      body: 'No explicit sections were supplied, so this render uses the summary as the first living-doc panel.',
    }],
    provenance_refs: provenanceRefs,
    duration_ms: durationMs,
    palette: normalizePalette(record.palette),
  };
}

export function summarizeProvenanceLivingDoc(doc: ProvenanceLivingDoc): ProvenanceLivingDocSummary {
  return {
    section_count: doc.sections.length,
    weighted_term_count: doc.weighted_terms.length,
    favorite_word_count: doc.favorite_words.length,
    provenance_ref_count: doc.provenance_refs.length,
    merkle_root_present: doc.merkle_root.trim().length > 0,
    shape_id_present: doc.shape_id.trim().length > 0,
  };
}

export function sampleProvenanceLivingDoc(): ProvenanceLivingDoc {
  return normalizeProvenanceLivingDoc({
    title: 'HiRAG Provenance Surface',
    subtitle: 'Semantic shape, weighted lexicon, and living context',
    summary: 'SPARK-shaped messaging has been gated before HiRAG ingest. The top terms, aliases, and provenance references are arranged for fast review so motion exports and notebook surfaces share the same semantic center.',
    merkle_root: 'mkl_7f6f4c4b3a2e1d09',
    shape_id: 'shape.spark.provenance.01',
    favorite_words: ['signal', 'resonance', 'witness', 'shape', 'lexicon'],
    weighted_terms: [
      { term: 'provenance', weight: 0.98, cluster: 'trust' },
      { term: 'lexicon', weight: 0.91, cluster: 'semantic-shape' },
      { term: 'hyperdimensions', weight: 0.84, cluster: 'visual-surface' },
      { term: 'spark', weight: 0.79, cluster: 'agent-pass' },
      { term: 'hirag', weight: 0.74, cluster: 'index' }
    ],
    sections: [
      {
        heading: 'Summary',
        body: 'Accepted content keeps its weighted language, favorite words, and source lineage so the living document can be inspected before it becomes a clip, a notebook block, or a Hyperdimensions annotation.',
      },
      {
        heading: 'Operators',
        body: 'Use this surface when you want the same semantic bundle to drive art, docs, and indexing instead of letting each surface drift into its own copy.',
      }
    ],
    provenance_refs: [
      { label: 'content.raw.v1', kind: 'subject' },
      { label: 'content.hirag.accepted.v1', kind: 'subject' },
      { label: 'geometry room', kind: 'surface' }
    ],
  });
}
