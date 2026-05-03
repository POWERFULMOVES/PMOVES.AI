import {
  layoutWithLines,
  measureLineStats,
  measureNaturalWidth,
  prepareWithSegments,
  setLocale,
} from '@chenglou/pretext';

export type LayoutEngine = 'browser' | 'pretext';

export interface TextLayoutConfig {
  engine?: LayoutEngine;
  maxWidth?: number | string;
  lineHeight?: number;
  letterSpacing?: number;
  whiteSpace?: 'normal' | 'pre-wrap';
  wordBreak?: 'normal' | 'keep-all';
  textAlign?: 'left' | 'center' | 'right';
  maxLines?: number;
  shrinkWrap?: boolean;
  debugBoxes?: boolean;
  locale?: string;
}

export interface TextStyleConfig {
  x?: number | string;
  y?: number | string;
  width?: number | string;
  maxWidth?: number | string;
  height?: number | string;
  color?: string;
  fontSize?: number | string;
  fontFamily?: string;
  fontWeight?: number | string;
  fontStyle?: string;
  lineHeight?: number | string;
  letterSpacing?: number | string;
  textAlign?: 'left' | 'center' | 'right' | string;
}

export interface TextElementSize {
  width?: number | string;
  height?: number | string;
}

export interface ResolvedTextLayout {
  lines: string[];
  lineCount: number;
  visibleLineCount: number;
  maxWidth: number;
  maxLineWidth: number;
  naturalWidth: number;
  renderWidth: number;
  lineHeight: number;
  height: number;
  letterSpacing: number;
  textAlign: 'left' | 'center' | 'right';
  overflowed: boolean;
  debugBoxes: boolean;
}

const DEFAULT_TEXT_WIDTH = 720;

/**
 * Detects whether the current runtime exposes APIs usable for canvas-based text measurement.
 *
 * @returns `true` if `globalThis` contains either `OffscreenCanvas` or `document`, `false` otherwise.
 */
function hasCanvasMeasurementRuntime(): boolean {
  const runtime = globalThis as Record<string, unknown>;
  return 'OffscreenCanvas' in runtime || 'document' in runtime;
}

/**
 * Resolve a numeric layout value possibly expressed as a percentage or `'px'` string into an absolute number.
 *
 * @param value - The input value to resolve; may be a number, a string (e.g., `"50%"`, `"12px"`, or `"3.5"`), or `undefined`.
 * @param reference - Reference number used when `value` is a percentage (e.g., percent of this reference).
 * @param fallback - Value to return when `value` is missing or cannot be parsed to a finite number.
 * @returns The resolved finite number. For percentage strings returns `(reference * percentage) / 100`; for `'px'` strings returns the parsed pixels; for plain numeric strings returns the parsed value; returns `fallback` if parsing fails or input is invalid.
 */
function resolveNumeric(value: number | string | undefined, reference: number, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return fallback;
    }

    if (trimmed.endsWith('%')) {
      const percentage = Number.parseFloat(trimmed.slice(0, -1));
      if (Number.isFinite(percentage)) {
        return (reference * percentage) / 100;
      }
    }

    if (trimmed.endsWith('px')) {
      const px = Number.parseFloat(trimmed.slice(0, -2));
      if (Number.isFinite(px)) {
        return px;
      }
    }

    const parsed = Number.parseFloat(trimmed);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return fallback;
}

/**
 * Resolve the font size from the provided style, falling back to 36px when absent or invalid.
 *
 * @returns The resolved font size in pixels; defaults to 36 when `style.fontSize` is not present or cannot be parsed.
 */
function resolveFontSize(style: TextStyleConfig | undefined): number {
  return resolveNumeric(style?.fontSize, 0, 36);
}

/**
 * Compute the effective line height for text using a layout override or style values.
 *
 * If `layout.lineHeight` is a finite number it is used; otherwise the function derives line height from `style` (using `style.lineHeight` when valid, or falling back to approximately 1.2× the resolved font size).
 *
 * @param style - Optional text style configuration used to derive font size and style line-height
 * @param layout - Optional layout configuration that can override line height
 * @returns The resolved line height as a number (in pixels)
 */
function resolveLineHeight(style: TextStyleConfig | undefined, layout: TextLayoutConfig | undefined): number {
  if (typeof layout?.lineHeight === 'number' && Number.isFinite(layout.lineHeight)) {
    return layout.lineHeight;
  }

  const fontSize = resolveFontSize(style);
  return resolveNumeric(style?.lineHeight, 0, Math.round(fontSize * 1.2));
}

/**
 * Determines the effective letter spacing, using the layout override when present and falling back to the style value or 0.
 *
 * @param style - Text style configuration that may include `letterSpacing`
 * @param layout - Layout configuration that may include `letterSpacing` and takes precedence over `style`
 * @returns The resolved letter spacing in pixels; `0` when unspecified or not a finite value
 */
function resolveLetterSpacing(style: TextStyleConfig | undefined, layout: TextLayoutConfig | undefined): number {
  const raw = layout?.letterSpacing ?? style?.letterSpacing;
  return resolveNumeric(raw, 0, 0);
}

/**
 * Constructs a canvas-compatible font string from a text style configuration.
 *
 * Defaults missing values to `fontStyle: "normal"`, `fontWeight: "400"`, `fontFamily: "sans-serif"`,
 * and resolves `fontSize` via `resolveFontSize`.
 *
 * @param style - Optional text style configuration used to derive font style, weight, size, and family
 * @returns A collapsed-whitespace font string formatted as `"fontStyle fontWeight {fontSize}px fontFamily"`
 */
function buildCanvasFont(style: TextStyleConfig | undefined): string {
  const fontSize = resolveFontSize(style);
  const fontStyle = typeof style?.fontStyle === 'string' && style.fontStyle.trim()
    ? style.fontStyle.trim()
    : 'normal';
  const fontWeight = typeof style?.fontWeight === 'number' || typeof style?.fontWeight === 'string'
    ? String(style.fontWeight)
    : '400';
  const fontFamily = typeof style?.fontFamily === 'string' && style.fontFamily.trim()
    ? style.fontFamily.trim()
    : 'sans-serif';

  return `${fontStyle} ${fontWeight} ${fontSize}px ${fontFamily}`.replace(/\s+/g, ' ').trim();
}

/**
 * Resolve text lines and layout metrics using the Pretext engine when available.
 *
 * @param text - The source text to measure and layout.
 * @param style - Optional style hints (font, fontSize, lineHeight, letterSpacing, textAlign, width/maxWidth, etc.) that influence font construction and alignment.
 * @param layout - Optional layout configuration (must specify `engine: 'pretext'` to run) that controls maxWidth, line/word wrapping, letter spacing, maxLines, shrinkWrap, textAlign, locale, debugBoxes, and related behavior.
 * @param size - Optional element size hints; `size.width` is used as a candidate for resolving `maxWidth`.
 * @param canvasWidth - The reference canvas width (in pixels) used for resolving percentage-based or relative widths.
 * @returns A `ResolvedTextLayout` containing computed lines and metrics when the pretext engine is selected and measurement succeeds; `null` if the engine is not `pretext`, the runtime lacks canvas/document measurement support, or an error occurs during measurement/layout.
 */
export function resolveTextLayout(
  text: string,
  style: TextStyleConfig | undefined,
  layout: TextLayoutConfig | undefined,
  size: TextElementSize | undefined,
  canvasWidth: number,
): ResolvedTextLayout | null {
  if (layout?.engine !== 'pretext') {
    return null;
  }

  if (!hasCanvasMeasurementRuntime()) {
    return null;
  }

  if (layout.locale) {
    setLocale(layout.locale);
  }

  const maxWidth = Math.max(
    1,
    resolveNumeric(
      layout.maxWidth ?? size?.width ?? style?.maxWidth ?? style?.width,
      canvasWidth,
      Math.min(canvasWidth * 0.8, DEFAULT_TEXT_WIDTH),
    ),
  );
  const lineHeight = Math.max(1, resolveLineHeight(style, layout));
  const letterSpacing = resolveLetterSpacing(style, layout);

  try {
    const prepared = prepareWithSegments(text, buildCanvasFont(style), {
      whiteSpace: layout.whiteSpace ?? 'normal',
      wordBreak: layout.wordBreak ?? 'normal',
      letterSpacing,
    });
    const stats = measureLineStats(prepared, maxWidth);
    const naturalWidth = measureNaturalWidth(prepared);
    const laidOut = layoutWithLines(prepared, maxWidth, lineHeight);
    const overflowed = layout.maxLines !== undefined && laidOut.lines.length > layout.maxLines;
    const visibleLines = overflowed && layout.maxLines !== undefined
      ? laidOut.lines.slice(0, layout.maxLines)
      : laidOut.lines;
    const textAlign = layout.textAlign ?? (style?.textAlign === 'center' || style?.textAlign === 'right' ? style.textAlign : 'left');
    const renderWidth = layout.shrinkWrap ? Math.min(stats.maxLineWidth || maxWidth, maxWidth) : maxWidth;

    return {
      lines: visibleLines.map((line) => line.text),
      lineCount: laidOut.lines.length,
      visibleLineCount: visibleLines.length,
      maxWidth,
      maxLineWidth: stats.maxLineWidth,
      naturalWidth,
      renderWidth,
      lineHeight,
      height: visibleLines.length * lineHeight,
      letterSpacing,
      textAlign,
      overflowed,
      debugBoxes: layout.debugBoxes ?? false,
    };
  } catch {
    return null;
  }
}
