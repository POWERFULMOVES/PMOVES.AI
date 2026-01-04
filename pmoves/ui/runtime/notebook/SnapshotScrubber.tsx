"use client";

import React, { startTransition, useEffect, useMemo, useState } from "react";
import { useSnapshots } from "./useSnapshots";
import { supabase } from "@/lib/supabase";

export function SnapshotScrubber({ threadId, onChange }: { threadId: string; onChange: (iso: string) => void }) {
  const { ticks, refreshTicks } = useSnapshots(threadId);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!threadId) return;
    const channel = supabase.channel(`scrubber:${threadId}`);
    channel.on("postgres_changes", { event: "*", schema: "public", table: "message_views" }, () => refreshTicks());
    channel.on("postgres_changes", { event: "*", schema: "public", table: "view_group_actions" }, () => refreshTicks());
    channel.subscribe();
    return () => {
      channel.unsubscribe();
    };
  }, [refreshTicks, threadId]);

  useEffect(() => {
    if (ticks.length) {
      const clamped = Math.max(0, Math.min(index, ticks.length - 1));
      onChange(ticks[clamped]?.tick);
    }
  }, [index, onChange, ticks]);

  useEffect(() => {
    const max = Math.max(0, ticks.length - 1);
    startTransition(() => {
      setIndex((prev) => (prev > max ? max : prev));
    });
  }, [ticks.length]);

  const labels = useMemo(() => ticks.map((tick) => new Date(tick.tick).toLocaleTimeString()), [ticks]);
  const max = Math.max(0, ticks.length - 1);

  return (
    <div style={{ border: "1px solid #333", borderRadius: 8, padding: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="range"
          min={0}
          max={max}
          value={Math.min(index, max)}
          onChange={(event) => setIndex(Number(event.target.value))}
          style={{ flex: 1 }}
        />
        <span style={{ fontVariantNumeric: "tabular-nums" }}>{labels[index] || "—"}</span>
      </div>
      <small>{ticks.length} ticks</small>
    </div>
  );
}
