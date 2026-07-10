"use client";

import { useSyncExternalStore } from "react";

/**
 * Showtime "live" indicator (DL-3.2). When the stage is live, the app sets
 * `document.documentElement.dataset.stage = "live"`. This badge surfaces that
 * state as a small pill whose ✦ signature mark intensifies (glows) via the
 * `pm-live-mark` utility — the mark NEVER changes color (stays `--pm-signature`).
 *
 * SSR-safe and reactive: the stage is an external mutable store (a DOM dataset
 * attribute), so we read it via useSyncExternalStore. The server snapshot is
 * `false`, so the first (server + hydration) render assumes not-live when the
 * `live` prop is omitted, and the badge updates if `data-stage` changes later.
 */
function subscribeStage(onChange: () => void): () => void {
  if (typeof document === "undefined") {
    return () => {};
  }
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-stage"],
  });
  return () => observer.disconnect();
}

function getStageLiveSnapshot(): boolean {
  return document.documentElement.dataset.stage === "live";
}

function getStageLiveServerSnapshot(): boolean {
  return false;
}

export function LiveStageBadge({
  live,
  className = "",
}: {
  live?: boolean;
  className?: string;
}) {
  const derivedLive = useSyncExternalStore(
    subscribeStage,
    getStageLiveSnapshot,
    getStageLiveServerSnapshot,
  );

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
