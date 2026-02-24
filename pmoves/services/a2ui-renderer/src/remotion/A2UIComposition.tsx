/**
 * A2UIComposition — Root Remotion Composition
 *
 * Renders A2UI animation specs as React components → video frames.
 * Supports scenes with elements: text, bar_chart, glyph_pulse, gradient_morph.
 */

import React from 'react';
import { Composition, AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { DarkxsidePortal } from './DarkxsidePortal';

interface A2UISpec {
  version: string;
  metadata?: { title?: string; compositionId?: string };
  animation: { duration_ms: number; bpm?: number; engine?: string };
  scenes: Array<{
    id: string;
    label: string;
    duration_ms: number;
    elements: Array<{
      type: string;
      content?: unknown;
      enter_at_ms?: number;
    }>;
  }>;
}

const A2UIScene: React.FC<{
  scene: A2UISpec['scenes'][0];
  fps: number;
}> = ({ scene, fps }) => {
  const frame = useCurrentFrame();

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

        if (el.type === 'text') {
          return (
            <div key={i} style={{ opacity, color: '#fff', fontSize: 36, padding: 40 }}>
              {String(el.content || '')}
            </div>
          );
        }

        if (el.type === 'glyph_pulse') {
          return <DarkxsidePortal key={i} opacity={opacity} />;
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
              elements: [{ type: 'text', content: 'A2UI Renderer', enter_at_ms: 0 }],
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
