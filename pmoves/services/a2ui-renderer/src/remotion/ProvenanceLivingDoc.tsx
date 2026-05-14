import React from 'react';
import { AbsoluteFill, Composition, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import {
  type ProvenanceLivingDoc,
  sampleProvenanceLivingDoc,
  summarizeProvenanceLivingDoc,
} from '../provenanceLivingDoc';
import { resolveTextLayout } from './pretextLayout';

type ParagraphProps = {
  text: string;
  width: number;
  fontSize: number;
  lineHeight: number;
  color: string;
  fontWeight?: number;
  accent?: string;
  maxLines?: number;
};

const panelShadow = '0 28px 80px rgba(15, 23, 42, 0.35)';

function revealProgress(frame: number, start: number, duration: number): number {
  return interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
}

function revealStyle(frame: number, start: number, duration: number, offsetX = 0, offsetY = 24): React.CSSProperties {
  const progress = revealProgress(frame, start, duration);
  return {
    opacity: progress,
    transform: `translate(${(1 - progress) * offsetX}px, ${(1 - progress) * offsetY}px)`,
  };
}

const PretextParagraph: React.FC<ParagraphProps> = ({
  text,
  width,
  fontSize,
  lineHeight,
  color,
  fontWeight = 400,
  accent,
  maxLines,
}) => {
  const { width: canvasWidth } = useVideoConfig();
  const layout = resolveTextLayout(
    text,
    {
      width,
      maxWidth: width,
      fontSize,
      lineHeight,
      color,
      fontWeight,
      fontFamily: '"Segoe UI", "Aptos", sans-serif',
    },
    {
      engine: 'pretext',
      maxWidth: width,
      lineHeight,
      shrinkWrap: false,
      maxLines,
    },
    { width },
    canvasWidth,
  );

  if (!layout) {
    return (
      <div style={{ width, color, fontSize, lineHeight: `${lineHeight}px`, fontWeight, whiteSpace: 'pre-wrap' }}>
        {text}
      </div>
    );
  }

  return (
    <div style={{ width, color, fontSize, lineHeight: `${layout.lineHeight}px`, fontWeight }}>
      {layout.lines.map((line, index) => (
        <div key={`${line}-${index}`} style={{ minHeight: layout.lineHeight }}>
          {line}
        </div>
      ))}
      {layout.overflowed ? (
        <div style={{ marginTop: 8, color: accent || color, fontSize: Math.max(14, fontSize - 8), letterSpacing: 1.2 }}>
          + more
        </div>
      ) : null}
    </div>
  );
};

const ProvenanceLivingDocCard: React.FC<{ doc: ProvenanceLivingDoc }> = ({ doc }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames - 1], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const slide = interpolate(frame, [0, 18], [18, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const summary = summarizeProvenanceLivingDoc(doc);
  const topTerms = doc.weighted_terms.slice(0, 4);
  const sections = doc.sections.slice(0, 2);
  const refs = doc.provenance_refs.slice(0, 3);
  const backgroundDriftX = Math.sin(frame / 52) * 18;
  const backgroundDriftY = Math.cos(frame / 64) * 14;

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 12% 18%, rgba(251, 113, 133, 0.2), transparent 28%), radial-gradient(circle at 86% 12%, rgba(103, 232, 249, 0.22), transparent 24%), linear-gradient(145deg, ${doc.palette.background} 0%, #111827 62%, #1e293b 100%)`,
        color: doc.palette.ink,
        fontFamily: '"Segoe UI", "Aptos", sans-serif',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 36,
          borderRadius: 30,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          background: 'rgba(15, 23, 42, 0.16)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: -120 + backgroundDriftX,
          top: 260 + backgroundDriftY,
          width: 420,
          height: 420,
          borderRadius: 999,
          background: 'radial-gradient(circle, rgba(251, 113, 133, 0.08) 0%, rgba(251, 113, 133, 0.0) 72%)',
          filter: 'blur(18px)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          right: -120 - backgroundDriftX * 0.7,
          top: 120 - backgroundDriftY,
          width: 520,
          height: 520,
          borderRadius: 999,
          background: 'radial-gradient(circle, rgba(103, 232, 249, 0.09) 0%, rgba(103, 232, 249, 0.0) 72%)',
          filter: 'blur(24px)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: 92,
          top: 92,
          width: 980,
          ...revealStyle(frame, 0, 18, 0, 18),
        }}
      >
        <div style={{ color: doc.palette.accentSoft, fontSize: 18, letterSpacing: 4, textTransform: 'uppercase' }}>
          Living Document
        </div>
        <div style={{ marginTop: 12, fontSize: 62, lineHeight: '68px', fontWeight: 700, letterSpacing: -1.4 }}>
          {doc.title}
        </div>
        <div style={{ marginTop: 14, fontSize: 24, lineHeight: '31px', color: doc.palette.muted }}>
          {doc.subtitle}
        </div>
        <div
          style={{
            marginTop: 20,
            width: 180 + progress * 200,
            height: 3,
            borderRadius: 999,
            background: `linear-gradient(90deg, ${doc.palette.accent} 0%, ${doc.palette.accentSoft} 100%)`,
          }}
        />
      </div>

      <div
        style={{
          position: 'absolute',
          right: 92,
          top: 92,
          width: 360,
          padding: '22px 24px',
          borderRadius: 26,
          background: doc.palette.panel,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: panelShadow,
          ...revealStyle(frame, 6, 18, 28, 0),
        }}
      >
        <div style={{ fontSize: 14, letterSpacing: 2.8, textTransform: 'uppercase', color: doc.palette.accent }}>
          Integrity
        </div>
        <div style={{ marginTop: 14, fontSize: 14, lineHeight: '18px', color: doc.palette.muted }}>
          Merkle Root
        </div>
        <div style={{ marginTop: 4, fontSize: 20, lineHeight: '26px', fontWeight: 700 }}>
          {doc.merkle_root}
        </div>
        <div style={{ marginTop: 16, fontSize: 14, lineHeight: '18px', color: doc.palette.muted }}>
          Shape ID
        </div>
        <div style={{ marginTop: 4, fontSize: 20, lineHeight: '26px', fontWeight: 700 }}>
          {doc.shape_id}
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 92,
          top: 276,
          width: 940,
          padding: '28px 30px',
          borderRadius: 28,
          background: doc.palette.panel,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: panelShadow,
          ...revealStyle(frame, 14, 18, 0, 28),
        }}
      >
        <div style={{ fontSize: 14, letterSpacing: 2.8, textTransform: 'uppercase', color: doc.palette.accent }}>
          Summary
        </div>
        <div style={{ marginTop: 16 }}>
          <PretextParagraph
            text={doc.summary}
            width={880}
            fontSize={28}
            lineHeight={36}
            color={doc.palette.ink}
            accent={doc.palette.accent}
            maxLines={6}
          />
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 92,
          top: 564,
          display: 'flex',
          gap: 18,
          ...revealStyle(frame, 22, 16, 0, 20),
        }}
      >
        {[
          { label: 'Sections', value: summary.section_count },
          { label: 'Weighted Terms', value: summary.weighted_term_count },
          { label: 'Refs', value: summary.provenance_ref_count },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              width: 216,
              padding: '18px 20px',
              borderRadius: 22,
              background: doc.palette.panelAlt,
              border: '1px solid rgba(255, 255, 255, 0.07)',
              boxShadow: panelShadow,
            }}
          >
            <div style={{ fontSize: 13, letterSpacing: 2.2, textTransform: 'uppercase', color: doc.palette.muted }}>
              {item.label}
            </div>
            <div style={{ marginTop: 12, fontSize: 34, lineHeight: '38px', fontWeight: 700, color: doc.palette.accentSoft }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {sections.map((section, index) => (
        <div
          key={`${section.heading}-${index}`}
          style={{
            position: 'absolute',
            left: 92 + index * 462,
            top: 688,
            width: 442,
            padding: '24px 26px',
            borderRadius: 26,
            background: doc.palette.panel,
            border: '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: panelShadow,
            ...revealStyle(frame, 32 + index * 8, 18, index === 0 ? -18 : 18, 24),
          }}
        >
          <div style={{ fontSize: 18, lineHeight: '24px', fontWeight: 700, color: doc.palette.accentSoft }}>
            {section.heading}
          </div>
          <div style={{ marginTop: 14 }}>
            <PretextParagraph
              text={section.body}
              width={390}
              fontSize={20}
              lineHeight={27}
              color={doc.palette.ink}
              accent={doc.palette.accent}
              maxLines={8}
            />
          </div>
        </div>
      ))}

      <div
        style={{
          position: 'absolute',
          right: 92,
          top: 276,
          width: 360,
          padding: '24px 24px 22px',
          borderRadius: 28,
          background: doc.palette.panel,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: panelShadow,
          ...revealStyle(frame, 12, 20, 24, 14),
        }}
      >
        <div style={{ fontSize: 14, letterSpacing: 2.8, textTransform: 'uppercase', color: doc.palette.accent }}>
          Weighted Lexicon
        </div>
        <div style={{ marginTop: 16, display: 'grid', gap: 12 }}>
          {topTerms.map((term, index) => {
            const weight = term.weight ?? 0.5;
            const barReveal = revealProgress(frame, 22 + index * 6, 16);
            return (
              <div key={`${term.term}-${index}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ fontSize: 21, lineHeight: '26px', fontWeight: 600 }}>
                    {term.term}
                  </div>
                  <div style={{ fontSize: 13, lineHeight: '18px', color: doc.palette.muted }}>
                    {(weight * 100).toFixed(0)}%
                  </div>
                </div>
                <div
                  style={{
                    marginTop: 8,
                    height: 10,
                    borderRadius: 999,
                    background: 'rgba(255, 255, 255, 0.08)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${(0.38 + weight * 0.62) * barReveal * 100}%`,
                      height: '100%',
                      borderRadius: 999,
                      background: `linear-gradient(90deg, ${doc.palette.accent} 0%, ${doc.palette.accentSoft} 100%)`,
                    }}
                  />
                </div>
                {term.cluster || term.role ? (
                  <div style={{ marginTop: 4, fontSize: 12, lineHeight: '16px', color: doc.palette.muted }}>
                    {[term.cluster, term.role].filter(Boolean).join(' :: ')}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          right: 92,
          top: 676,
          width: 360,
          padding: '22px 24px',
          borderRadius: 26,
          background: doc.palette.panelAlt,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: panelShadow,
          ...revealStyle(frame, 38, 18, 18, 24),
        }}
      >
        <div style={{ fontSize: 14, letterSpacing: 2.8, textTransform: 'uppercase', color: doc.palette.accentSoft }}>
          Favorite Words
        </div>
        <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {doc.favorite_words.length > 0 ? doc.favorite_words.map((word, index) => (
            <div
              key={`${word}-${index}`}
              style={{
                padding: '8px 12px',
                borderRadius: 999,
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                fontSize: 15,
                lineHeight: '19px',
                opacity: revealProgress(frame, 46 + index * 3, 12),
              }}
            >
              {word}
            </div>
          )) : (
            <div style={{ fontSize: 15, lineHeight: '19px', color: doc.palette.muted }}>
              No favorite words supplied
            </div>
          )}
        </div>

        <div style={{ marginTop: 18, fontSize: 14, letterSpacing: 2.8, textTransform: 'uppercase', color: doc.palette.accentSoft }}>
          Provenance Refs
        </div>
        <div style={{ marginTop: 10, display: 'grid', gap: 10 }}>
          {refs.length > 0 ? refs.map((ref, index) => (
            <div
              key={`${ref.label}-${index}`}
              style={{
                padding: '10px 12px',
                borderRadius: 18,
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              <div style={{ fontSize: 16, lineHeight: '20px', fontWeight: 600 }}>{ref.label}</div>
              <div style={{ marginTop: 3, fontSize: 12, lineHeight: '16px', color: doc.palette.muted }}>
                {[ref.kind, ref.uri].filter(Boolean).join(' :: ')}
              </div>
            </div>
          )) : (
            <div style={{ fontSize: 15, lineHeight: '19px', color: doc.palette.muted }}>
              No refs supplied
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const ProvenanceLivingDocComposition: React.FC = () => (
  <Composition
    id="ProvenanceLivingDoc"
    component={ProvenanceLivingDocCard}
    durationInFrames={360}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{
      doc: sampleProvenanceLivingDoc(),
    }}
  />
);
