/**
 * A2UIComposition — Root Remotion Composition
 *
 * Renders A2UI animation specs as React components → video frames.
 * Supports scenes with elements: text, bar_chart, glyph_pulse, gradient_morph.
 */

import React from 'react';
import { AbsoluteFill, Composition, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { DarkxsidePortal } from './DarkxsidePortal';
import { resolveTextLayout, type TextLayoutConfig, type TextStyleConfig } from './pretextLayout';

interface A2UISpec {
  version: string;
  metadata?: { title?: string; compositionId?: string };
  animation: { duration_ms: number; bpm?: number; engine?: string };
  scenes: Array<{
    id: string;
    label: string;
    duration_ms: number;
    elements: A2UIElement[];
  }>;
}

interface A2UIElement {
  type: string;
  id?: string;
  content?: unknown;
  symbol?: string;
  enter_at_ms?: number;
  style?: TextStyleConfig;
  position?: {
    x?: number | string;
    y?: number | string;
  };
  size?: {
    width?: number | string;
    height?: number | string;
  };
  text_layout?: TextLayoutConfig;
  [key: string]: unknown;
}

/**
 * Resolve an element's x and y coordinates, preferring explicit `position` values over `style` fallbacks.
 *
 * @param el - The element whose coordinates to resolve; `position` fields override `style` fields when present.
 * @returns An object with `x` and `y` taken from `el.position` if available, otherwise from `el.style`; each value may be a `number`, `string`, or `undefined`.
 */
function resolveElementPosition(el: A2UIElement): { x?: number | string; y?: number | string } {
  return {
    x: el.position?.x ?? el.style?.x,
    y: el.position?.y ?? el.style?.y,
  };
}

/**
 * Normalizes an input to a valid CSS text-align value.
 *
 * @param value - The input to interpret as text alignment (commonly a string).
 * @returns `'center'` or `'right'` when `value` strictly equals those strings, `'left'` otherwise.
 */
function resolveCssTextAlign(value: unknown): React.CSSProperties['textAlign'] {
  return value === 'center' || value === 'right' ? value : 'left';
}

const A2UIScene: React.FC<{
  scene: A2UISpec['scenes'][number];
  fps: number;
}> = ({ scene, fps }) => {
  const frame = useCurrentFrame();
  const { width: canvasWidth } = useVideoConfig();

  return (
    <AbsoluteFill style={{
      backgroundColor: '#1a1a2e',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'sans-serif',
    }}>
      {scene.elements.map((el, i) => {
        const enterFrame = Math.floor(((el.enter_at_ms || 0) / 1000) * fps);
        const opacity = interpolate(frame, [enterFrame, enterFrame + 15], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        const style = el.style || {};
        const position = resolveElementPosition(el);

        if (el.type === 'bar_chart') {
          const content = el.content as { labels?: string[]; values?: number[] } | undefined;
          const labels = content?.labels || [];
          const values = content?.values || [];
          const maxVal = Math.max(...values, 1);

          return (
            <div key={i} style={{ opacity, width: '80%', padding: 40 }}>
              <h2 style={{ color: '#FB7185', fontSize: 28, marginBottom: 20 }}>{scene.label}</h2>
              {labels.map((label, j) => {
                const barWidth = interpolate(
                  frame,
                  [enterFrame + j * 5, enterFrame + j * 5 + 20],
                  [0, (values[j] / maxVal) * 100],
                  { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
                );
                return (
                  <div key={j} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ color: '#fff', width: 120, fontSize: 14 }}>{label}</span>
                    <div style={{
                      height: 24,
                      width: `${barWidth}%`,
                      backgroundColor: '#E11D48',
                      borderRadius: 4,
                      transition: 'width 0.1s',
                    }} />
                    <span style={{ color: '#FB7185', marginLeft: 8, fontSize: 12 }}>{values[j]}</span>
                  </div>
                );
              })}
            </div>
          );
        }

        if (el.type === 'text' || el.type === 'heading') {
          const textContent = String(el.content || '');
          const layout = resolveTextLayout(
            textContent,
            style,
            el.text_layout,
            el.size,
            canvasWidth,
          );
          const renderWidth = layout?.renderWidth ?? el.size?.width ?? style.width ?? style.maxWidth;
          const fontSize = style.fontSize || (el.type === 'heading' ? 52 : 36);
          const fontWeight = style.fontWeight || (el.type === 'heading' ? 700 : 400);
          const containerStyle: React.CSSProperties = {
            position: position.x !== undefined || position.y !== undefined ? 'absolute' : 'relative',
            left: position.x,
            top: position.y,
            opacity,
            color: style.color || '#fff',
            fontSize,
            fontFamily: style.fontFamily || 'inherit',
            fontWeight,
            fontStyle: style.fontStyle,
            width: renderWidth,
            maxWidth: layout?.maxWidth,
            letterSpacing: layout?.letterSpacing ?? style.letterSpacing,
            textAlign: layout?.textAlign ?? resolveCssTextAlign(style.textAlign),
            lineHeight: layout?.lineHeight ?? style.lineHeight,
            whiteSpace: layout ? 'normal' : 'pre-wrap',
            display: 'flex',
            flexDirection: 'column',
            gap: 0,
          };

          if (layout) {
            return (
              <div key={i} style={containerStyle}>
                {layout.lines.map((line, lineIndex) => (
                  <div
                    key={`${i}-${lineIndex}`}
                    style={{
                      minHeight: layout.lineHeight,
                      lineHeight: `${layout.lineHeight}px`,
                    }}
                  >
                    {line}
                  </div>
                ))}
                {layout.debugBoxes ? (
                  <>
                    <div
                      style={{
                        position: 'absolute',
                        inset: 0,
                        border: '1px dashed rgba(251, 113, 133, 0.7)',
                        pointerEvents: 'none',
                      }}
                    />
                    <div
                      style={{
                        position: 'absolute',
                        left: 0,
                        bottom: -22,
                        padding: '2px 6px',
                        borderRadius: 6,
                        background: 'rgba(26, 26, 46, 0.85)',
                        color: '#FB7185',
                        fontSize: 12,
                        lineHeight: '16px',
                        letterSpacing: 0,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {`PRETEXT ${layout.visibleLineCount}/${layout.lineCount} lines :: ${Math.round(layout.renderWidth)}px`}
                    </div>
                  </>
                ) : null}
              </div>
            );
          }

          return (
            <div key={i} style={{
              position: position.x !== undefined || position.y !== undefined ? 'absolute' : 'relative',
              left: position.x,
              top: position.y,
              opacity,
              color: style.color || '#fff',
              fontSize,
              fontFamily: style.fontFamily || 'inherit',
              fontWeight,
            }}>
              {textContent}
            </div>
          );
        }

        if (el.type === 'glyph') {
          return (
            <div key={i} style={{
              position: position.x !== undefined || position.y !== undefined ? 'absolute' : 'relative',
              left: position.x, top: position.y,
              opacity, color: style.color || '#00FFCC',
              fontSize: style.fontSize || 24,
              transform: 'translate(-50%, -50%)' // Center the glyph on the coordinate
            }}>
              {el.symbol || '●'}
            </div>
          );
        }

        if (el.type === 'glyph_pulse') {
          return <DarkxsidePortal key={i} opacity={opacity} />;
        }

        if (el.type === 'geometry_mesh') {
           return <div key={i} style={{ opacity, position: 'absolute', bottom: 20, right: 20, color: '#666' }}>[Geometry Mesh: {String(el.edges_count || 'unknown')} edges]</div>;
        }

        return (
          <div key={i} style={{ opacity, color: '#666', fontSize: 14 }}>
            Unknown element type: {el.type}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

const A2UIRenderer: React.FC<{ spec: A2UISpec }> = ({ spec }) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();

  // Find the active scene based on current frame
  let accumulatedFrames = 0;
  let activeScene = spec.scenes[0];

  for (const scene of spec.scenes) {
    const sceneFrames = Math.ceil((scene.duration_ms / 1000) * fps);
    if (frame < accumulatedFrames + sceneFrames) {
      activeScene = scene;
      break;
    }
    accumulatedFrames += sceneFrames;
  }

  return <A2UIScene scene={activeScene} fps={fps} />;
};

export const A2UIComposition: React.FC = () => {
  return (
    <>
      <Composition
        id="A2UIComposition"
        component={A2UIRenderer}
        durationInFrames={180}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          spec: {
            version: 'a2ui.animation.v1',
            animation: { duration_ms: 6000, bpm: 10 },
            scenes: [{
              id: 'default',
              label: 'A2UI',
              duration_ms: 6000,
              elements: [{
                type: 'text',
                content: 'A2UI Renderer',
                enter_at_ms: 0,
                style: {
                  x: 480,
                  y: 420,
                  fontSize: 42,
                  fontFamily: 'Inter, sans-serif',
                  color: '#ffffff',
                },
                size: {
                  width: 420,
                },
                text_layout: {
                  engine: 'pretext',
                  maxWidth: 420,
                  lineHeight: 50,
                  shrinkWrap: true,
                  debugBoxes: true,
                },
              }],
            }],
          },
        }}
      />
      <Composition
        id="DarkxsideSignature"
        component={() => (
          <AbsoluteFill style={{ backgroundColor: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <DarkxsidePortal opacity={1} />
          </AbsoluteFill>
        )}
        durationInFrames={180}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
