"use client";

import React from "react";

export type Chapter = { t: number; title: string };

export function YouTubeChaptersOverlay({ chapters, onJump }: { chapters: Chapter[]; onJump: (t: number) => void }) {
  return (
    <div style={{ position: "relative", width: "100%", height: 24, background: "#0f1115", border: "1px solid #333", borderRadius: 6 }}>
      {chapters.map((chapter, index) => (
        <button
          key={`${chapter.title}-${chapter.t}`}
          onClick={() => onJump(chapter.t)}
          title={chapter.title}
          style={{
            position: "absolute",
            left: `${(index / Math.max(1, chapters.length - 1)) * 100}%`,
            top: 0,
            bottom: 0,
            width: 2,
            background: "#ffd400",
          }}
        />
      ))}
    </div>
  );
}
