"use client";

import { useEffect, useState } from "react";

type GraphitiState = "loading" | "available" | "unavailable";

interface GraphitiData {
  available: boolean;
  source: string | null;
  generatedAt: string | null;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0 || !Number.isFinite(diff)) return iso;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const POLL_INTERVAL = 60_000;

const dotClasses: Record<GraphitiState, string> = {
  loading: "bg-cata-gold animate-spin",
  available: "bg-cata-forest shadow-[0_0_8px_rgba(0,255,136,0.5)]",
  unavailable: "bg-ink-muted",
};

const badgeClasses: Record<GraphitiState, string> = {
  loading: "text-cata-gold bg-cata-gold/10 border-cata-gold/30",
  available: "text-cata-forest bg-cata-forest/10 border-cata-forest/30",
  unavailable: "text-ink-muted bg-void-soft border-ink-muted/30",
};

export function GraphitiStatusBadge({ className = "" }: { className?: string }) {
  const [state, setState] = useState<GraphitiState>("loading");
  const [data, setData] = useState<GraphitiData | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchStatus() {
      try {
        const res = await fetch("/api/audit/summary?includeHealth=false");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (cancelled) return;
        const graphiti: GraphitiData = json.graphiti ?? { available: false, source: null, generatedAt: null };
        setData(graphiti);
        setState(graphiti.available ? "available" : "unavailable");
      } catch {
        if (cancelled) return;
        setState("unavailable");
        setData(null);
      }
    }

    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const label =
    state === "loading"
      ? "Checking…"
      : state === "available"
        ? "Graphiti Active"
        : "Graphiti Unavailable";

  const subtitle =
    state === "available" && data?.generatedAt
      ? relativeTime(data.generatedAt)
      : state === "unavailable"
        ? "Trail artifact missing"
        : undefined;

  return (
    <div
      className={`
        inline-flex items-center gap-1.5 rounded-full border
        font-pixel uppercase text-[10px] px-2 py-1
        ${badgeClasses[state]}
        ${className}
      `}
      aria-label={`Graphiti protocol status: ${label}`}
    >
      <div className={`relative rounded-full w-2 h-2 ${dotClasses[state]}`} />
      <span>{label}</span>
      {subtitle && (
        <span className="opacity-60 normal-case text-[9px]">{subtitle}</span>
      )}
    </div>
  );
}
