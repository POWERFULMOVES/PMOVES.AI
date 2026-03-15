"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardNavigation";
import type { GraphitiTrailsResponse, TrailEntry } from "@/lib/types/graphiti";

export default function GraphitiDashboardPage() {
  const [data, setData] = useState<GraphitiTrailsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agentFilter, setAgentFilter] = useState<string>("ALL");
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  useEffect(() => {
    const fetchTrails = async () => {
      try {
        const params = new URLSearchParams();
        if (agentFilter !== "ALL") params.set("agentId", agentFilter);
        if (verifiedOnly) params.set("verifiedOnly", "true");

        const res = await fetch(`/api/graphiti/trails?${params}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
        setError(null);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };

    fetchTrails();
  }, [agentFilter, verifiedOnly]);

  const uniqueAgents = data
    ? Array.from(new Set(data.items.map((t) => t.agentId))).sort()
    : [];

  return (
    <DashboardShell
      title="Graphiti Trail"
      subtitle={`CHIT-signed agent trail entries • ${data?.stats.total || 0} entries`}
      active="graphiti"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Stats bar */}
        {data && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Total</span>
              <div className="font-display font-bold text-2xl text-cata-cyan">
                {data.stats.total}
              </div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Verified</span>
              <div className="font-display font-bold text-2xl text-cata-forest">
                {data.stats.verified}
              </div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Unsigned</span>
              <div className="font-display font-bold text-2xl text-cata-amber">
                {data.stats.unsigned}
              </div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Agents</span>
              <div className="font-display font-bold text-2xl text-cata-violet">
                {Object.keys(data.stats.byAgent).length}
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-ink-muted uppercase tracking-wider">
              Agent:
            </label>
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              className="px-3 py-1.5 text-xs font-mono border border-border-subtle bg-void text-ink-primary focus:outline-none focus:border-cata-cyan"
            >
              <option value="ALL">All Agents</option>
              {uniqueAgents.map((agent) => (
                <option key={agent} value={agent}>
                  {agent}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-xs text-ink-muted uppercase tracking-wider cursor-pointer">
            <input
              type="checkbox"
              checked={verifiedOnly}
              onChange={(e) => setVerifiedOnly(e.target.checked)}
              className="w-4 h-4"
            />
            Verified only
          </label>
        </div>

        {/* Error state */}
        {error && (
          <div className="card-brutal border-cata-ember">
            <div className="p-4 text-cata-ember">{error}</div>
          </div>
        )}

        {/* Trail entries */}
        <div className="card-brutal">
          {data && data.items.length === 0 ? (
            <div className="p-12 text-center text-ink-muted">
              No trail entries found
            </div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {data?.items.map((entry) => <TrailCard key={entry.id} entry={entry} />)}
            </div>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}

function TrailCard({ entry }: { entry: TrailEntry }) {
  return (
    <div className="p-4 hover:bg-void-elevated transition-colors">
      <div className="flex items-start gap-4">
        {/* Glyph */}
        <div
          className="w-12 h-12 flex items-center justify-center text-2xl rounded-lg flex-shrink-0"
          style={{ backgroundColor: `${entry.color}20` || "#7C3AED20" }}
        >
          <span style={{ color: entry.color }}>{entry.glyph}</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm text-cata-violet">
              {entry.displayName}
            </span>
            {entry.isVerified ? (
              <span className="text-2xs px-2 py-0.5 bg-cata-forest/20 text-cata-forest border border-cata-forest/50">
                ✓ Verified
              </span>
            ) : (
              <span className="text-2xs px-2 py-0.5 bg-cata-amber/20 text-cata-amber border border-cata-amber/50">
                Unsigned
              </span>
            )}
            <span className="text-2xs px-2 py-0.5 bg-void-elevated border border-border-subtle text-ink-muted">
              {entry.phase}
            </span>
          </div>

          <p className="text-sm text-ink-primary mb-2">{entry.summary}</p>

          <div className="flex flex-wrap items-center gap-3 text-xs text-ink-muted">
            <span>{new Date(entry.timestamp).toLocaleString()}</span>
            {entry.resonance.length > 0 && (
              <span>• {entry.resonance.join(", ")}</span>
            )}
            <span>• {entry.voice}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
