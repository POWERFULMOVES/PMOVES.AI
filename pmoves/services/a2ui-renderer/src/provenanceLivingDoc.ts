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

const DEFAULT_PALETTE: ProvenancePalette = {
  background: '#0f172a',
  panel: 'rgba(15, 23, 42, 0.82)',
  panelAlt: 'rgba(30, 41, 59, 0.78)',
  accent: '#fb7185',
  accentSoft: '#67e8f9',
  ink: '#f8fafc',
  muted: '#cbd5e1',
};

/**
 * Restricts a number to lie within the specified inclusive range.
 *
 * @param value - The number to constrain
 * @param min - The lower bound (inclusive)
 * @param max - The upper bound (inclusive)
 * @returns The input value constrained to the range `[min, max]`
 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Normalize a value into a trimmed, length-limited string, using a fallback when the input is not a usable string.
 *
 * @param value - The input to coerce into a string
 * @param fallback - The string to return when `value` is not a non-empty string after trimming
 * @param maxLength - Maximum number of characters to keep from the trimmed string
 * @returns A trimmed string truncated to at most `maxLength` characters, or `fallback` if the input is not a non-empty string
 */
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

/**
 * Normalize an input into a list of trimmed, non-empty strings limited by count and length.
 *
 * @param value - The value to normalize; treated as an array of potential strings. Non-arrays produce an empty list.
 * @param maxItems - Maximum number of items to include in the result.
 * @param maxLength - Maximum length for each string; longer strings are truncated.
 * @returns An array of trimmed, non-empty strings, containing at most `maxItems` entries and with each entry truncated to `maxLength` characters.
 */
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

/**
 * Coerces an input to a finite number when possible.
 *
 * @param value - The value to convert; accepts a finite number or a string containing a numeric literal.
 * @param fallback - The number to return if `value` cannot be converted to a finite number.
 * @returns The finite numeric value parsed from `value`, or `fallback` if conversion fails.
 */
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

/**
 * Normalize an arbitrary input into a weight value between 0 and 1.
 *
 * @param value - Input to coerce into a weight; accepts numbers or numeric strings, otherwise a fallback is used
 * @returns A number in the inclusive range 0 to 1; when input is not a finite number the result defaults to 0.5
 */
function normalizeWeight(value: unknown): number {
  return clamp(asNumber(value, 0.5), 0, 1);
}

/**
 * Normalize an untyped value into an array of up to four validated ProvenanceSection objects.
 *
 * Accepts an array of entries (objects) and extracts `heading` and `body` strings from each entry.
 * Non-object entries are ignored. Entries where both heading and body are empty after normalization
 * are omitted.
 *
 * @param value - The input to normalize; expected to be an array of objects with optional `heading` and `body` properties.
 * @returns An array (maximum length 4) of sections where each section has a `heading` (defaults to `"Section"` when empty, maximum 80 characters) and a `body` (defaults to the heading when empty, maximum 600 characters).
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

/**
 * Normalize an untyped value into an array of provenance reference entries.
 *
 * Accepts an array of strings or objects and produces up to six validated references;
 * string entries become `label`-only references, and object entries are normalized
 * to include `label`, optional `uri`, and optional `kind`. Entries lacking both
 * label and URI are omitted.
 *
 * @param value - Untyped input expected to be an array of strings or objects
 * @returns An array of `ProvenanceReference` objects (maximum 6 entries) with trimmed and length-limited `label`, optional `uri`, and optional `kind`
 */
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

/**
 * Normalizes an untyped value into a list of provenance terms.
 *
 * @param value - The input to normalize; expected to be an array of strings or objects describing terms.
 * @returns An array of up to eight `ProvenanceTerm` objects sorted by descending `weight`. Each entry contains a trimmed, truncated `term`, a normalized `weight`, and optional `cluster` and `role` when present.
 */
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

/**
 * Normalize an arbitrary input into a validated ProvenancePalette.
 *
 * @param value - Input that may contain palette fields; if missing or not an object, the default palette is used.
 * @returns A ProvenancePalette with each color field coerced to a safe string and default values filled from DEFAULT_PALETTE.
 */
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

/**
 * Estimate a playback duration for a provenance living document in milliseconds.
 *
 * Calculates an estimated duration based on the number of sections, weighted terms,
 * provenance references, and the length of the summary provided on `input`.
 *
 * @param input - An object that may contain `sections` (array), `weighted_terms` (array),
 *   `provenance_refs` (array), and `summary` (string); missing or invalid fields are treated as empty.
 * @returns The estimated duration in milliseconds, clamped to the range 9000–24000.
 */
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

/**
 * Normalize an arbitrary input into a validated ProvenanceLivingDoc structure.
 *
 * Converts and sanitizes fields from the provided raw input, applying sensible defaults,
 * string trimming/truncation, numeric clamping, array length limits, and palette normalization.
 * If the input is not an object it is treated as empty; if no sections remain after normalization,
 * a single fallback section is inserted that uses the summary as context.
 *
 * @param input - Raw untyped input to normalize into a ProvenanceLivingDoc
 * @returns A fully normalized ProvenanceLivingDoc with validated fields, defaults applied, and constraints enforced
 */
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

/**
 * Produce a compact summary of counts and presence flags for a provenance living document.
 *
 * @param doc - The provenance living document to summarize
 * @returns An object with counts for sections (`section_count`), weighted terms (`weighted_term_count`), favorite words (`favorite_word_count`), and provenance references (`provenance_ref_count`), plus `merkle_root_present` and `shape_id_present` which are `true` when the corresponding fields are non-empty after trimming, `false` otherwise
 */
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

/**
 * Create a normalized example Provenance Living Doc for use in samples, demos, and tests.
 *
 * @returns A concrete, normalized ProvenanceLivingDoc populated with sample title, subtitle, summary, merkle/shape identifiers, favorite words, weighted terms, sections, and provenance references.
 */
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
