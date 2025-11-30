"use client";

import React from "react";
import { ComicBubble } from "@/runtime/skin/ComicBubble";
import { MediaEmbed, type MediaMeta } from "./MediaEmbed";

export function MediaBubble({
  meta,
  archetype = "digital.hud",
  variant = "primary",
  seed = 42,
}: {
  meta: MediaMeta;
  archetype?: string;
  variant?: string;
  seed?: number;
}) {
  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ComicBubble archetype={archetype} variant={variant} seed={seed}>
        <div style={{ width: "100%", height: 240 }}>
          <MediaEmbed meta={meta} />
        </div>
      </ComicBubble>
    </div>
  );
}
