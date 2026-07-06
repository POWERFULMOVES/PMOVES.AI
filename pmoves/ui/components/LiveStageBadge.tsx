"use client";

import { useEffect, useState } from "react";

/**
 * Showtime "live" indicator (DL-3.2). When the stage is live, the app sets
 * `document.documentElement.dataset.stage = "live"`. This badge surfaces that
 * state as a small pill whose ✦ signature mark intensifies (glows) via the
 * `pm-live-mark` utility — the mark NEVER changes color (stays `--pm-signature`).
 *
 * SSR-safe: `document` is read only inside an effect, so the first (server +
 * hydration) render assumes `false` when the `live` prop is omitted.
 */
export function LiveStageBadge({
  live,
  className = "",
}: {
  live?: boolean;
  className?: string;
}) {
  const [derivedLive, setDerivedLive] = useState(false);

  useEffect(() => {
    if (live !== undefined) return;
    setDerivedLive(document.documentElement.dataset.stage === "live");
  }, [live]);

  const isLive = live ?? derivedLive;

  if (!isLive) return null;

  return (
    <div
      data-testid="live-stage-badge"
      className={`
        inline-flex items-center gap-1.5 rounded-full border
        font-pixel uppercase text-[10px] px-2 py-1
        text-ink-muted bg-void-soft border-ink-muted/30
        ${className}
      `}
      aria-label="Stage status: live"
    >
      <span className="pm-live-mark" aria-hidden="true">✦</span>
      <span>LIVE</span>
    </div>
  );
}
