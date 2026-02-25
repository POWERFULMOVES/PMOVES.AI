/**
 * DarkxsidePortal — DARKXSIDE Star Glyph Animation
 *
 * Renders the ✦ (Black Four Pointed Star) glyph with a pulsing
 * rose-crimson glow at 10 BPM (from AGNOTE4482.BEATS).
 *
 * Colors:
 *   Primary: #E11D48 (Rose Crimson)
 *   Accent:  #FB7185 (Rose 400)
 *   Background: #1a1a2e (PMOVES dark)
 */

import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate } from 'remotion';

interface DarkxsidePortalProps {
  opacity?: number;
  bpm?: number;
}

export const DarkxsidePortal: React.FC<DarkxsidePortalProps> = ({
  opacity = 1,
  bpm = 10,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 10 BPM = 1 beat every 6 seconds = 1 beat per 180 frames at 30fps
  const framesPerBeat = (60 / bpm) * fps;
  const beatProgress = (frame % framesPerBeat) / framesPerBeat;

  // Pulse: scale 1.0 → 1.15 → 1.0 over one beat cycle
  const scale = interpolate(
    beatProgress,
    [0, 0.3, 0.6, 1],
    [1, 1.15, 1.05, 1],
  );

  // Glow intensity: 0.4 → 1.0 → 0.4
  const glowIntensity = interpolate(
    beatProgress,
    [0, 0.3, 0.6, 1],
    [0.4, 1.0, 0.6, 0.4],
  );

  const glowSize = 20 + glowIntensity * 40;
  const glowColor = `rgba(225, 29, 72, ${glowIntensity * 0.8})`;
  const accentGlow = `rgba(251, 113, 133, ${glowIntensity * 0.5})`;

  // Subtle rotation
  const rotation = interpolate(frame, [0, fps * 12], [0, 360]);

  return (
    <div style={{
      opacity,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 24,
    }}>
      {/* Star Glyph */}
      <div style={{
        fontSize: 120,
        color: '#E11D48',
        textShadow: `0 0 ${glowSize}px ${glowColor}, 0 0 ${glowSize * 2}px ${accentGlow}`,
        transform: `scale(${scale}) rotate(${rotation}deg)`,
        lineHeight: 1,
      }}>
        ✦
      </div>

      {/* DARKXSIDE Text */}
      <div style={{
        fontSize: 48,
        fontWeight: 700,
        letterSpacing: 12,
        color: '#FB7185',
        textShadow: `0 0 ${glowSize / 2}px ${glowColor}`,
        opacity: interpolate(glowIntensity, [0.4, 1], [0.7, 1]),
      }}>
        DARKXSIDE
      </div>

      {/* Subtitle */}
      <div style={{
        fontSize: 18,
        letterSpacing: 6,
        color: 'rgba(251, 113, 133, 0.6)',
        textTransform: 'uppercase' as const,
      }}>
        COCREATOR :: WITNESS :: PMOVES.AI
      </div>

      {/* Beat indicator line */}
      <div style={{
        width: 200,
        height: 2,
        backgroundColor: 'rgba(225, 29, 72, 0.3)',
        marginTop: 16,
        position: 'relative' as const,
      }}>
        <div style={{
          width: `${beatProgress * 100}%`,
          height: '100%',
          backgroundColor: '#E11D48',
          boxShadow: `0 0 8px ${glowColor}`,
        }} />
      </div>
    </div>
  );
};
