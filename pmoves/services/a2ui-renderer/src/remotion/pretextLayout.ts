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

function hasCanvasMeasurementRuntime(): boolean {
  const runtime = globalThis as Record<string, unknown>;
  return 'OffscreenCanvas' in runtime || 'document' in runtime;
}

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

function resolveFontSize(style: TextStyleConfig | undefined): number {
  return resolveNumeric(style?.fontSize, 0, 36);
}

function resolveLineHeight(style: TextStyleConfig | undefined, layout: TextLayoutConfig | undefined): number {
  if (typeof layout?.lineHeight === 'number' && Number.isFinite(layout.lineHeight)) {
    return layout.lineHeight;
  }

  const fontSize = resolveFontSize(style);
  return resolveNumeric(style?.lineHeight, 0, Math.round(fontSize * 1.2));
}

function resolveLetterSpacing(style: TextStyleConfig | undefined, layout: TextLayoutConfig | undefined): number {
  const raw = layout?.letterSpacing ?? style?.letterSpacing;
  return resolveNumeric(raw, 0, 0);
}

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
