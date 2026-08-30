"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "../../../components/DashboardNavigation";

interface PrSummary {
  number: number;
  title: string;
  state: string;
  threadCount: number;
  riskLevel: "low" | "medium" | "high";
  updatedAt: string;
}

export default function ReviewDashboardPage() {
  const summaryUrl = "/api/audit/summary";
  const [prs, setPrs] = useState<PrSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let active = true;

    const fetchSummary = async () => {
      try {
        const res = await fetch(summaryUrl, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (active) {
          setPrs(json.prs ?? []);
          setLastUpdate(new Date());
          setErr(null);
        }
      } catch (e: unknown) {
        if (active) setErr(e instanceof Error ? e.message : String(e));
      }
    };

    fetchSummary();
    const interval = setInterval(fetchSummary, 15000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const riskColor: Record<string, string> = {
    low: "tag-forest",
    medium: "tag-gold",
    high: "tag-ember",
  };

  return (
    <DashboardShell
      title="Review Console"
      subtitle="PR triage, thread classification, and risk notes"
      active="review"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Status bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="tag tag-forest">
              <span
                className={`w-2 h-2 rounded-full ${err ? "bg-cata-ember" : "bg-cata-forest animate-pulse"}`}
              />
              {err ? "Error" : "Live"}
            </span>
            <a
              href={summaryUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-mono text-ink-muted hover:text-cata-cyan transition-colors"
            >
              {summaryUrl}
            </a>
          </div>
          {lastUpdate && (
            <span className="text-xs text-ink-muted font-mono">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* PR cards */}
        {err ? (
          <div className="card-brutal p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 flex items-center justify-center bg-cata-ember/20 text-cata-ember font-display font-bold flex-shrink-0">
                !
              </div>
              <div className="space-y-2">
                <h3 className="font-display font-semibold text-cata-ember">
                  Failed to fetch review data
                </h3>
                <p className="text-sm text-ink-secondary">{err}</p>
                <p className="text-xs text-ink-muted">
                  Ensure the audit API is running and accessible.
                </p>
              </div>
            </div>
          </div>
        ) : prs ? (
          prs.length === 0 ? (
            <div className="card-brutal p-12 flex flex-col items-center justify-center gap-4">
              <span className="font-display text-lg text-ink-muted">
                No open PRs to review
              </span>
              <span className="text-xs text-ink-muted">
                All clear — the queue is empty.
              </span>
            </div>
          ) : (
            <div className="grid gap-4">
              {prs.map((pr) => (
                <div key={pr.number} className="card-brutal p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs text-ink-muted">
                          #{pr.number}
                        </span>
                        <h3 className="font-display font-semibold text-sm truncate">
                          {pr.title}
                        </h3>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`tag ${riskColor[pr.riskLevel] ?? "tag-forest"}`}>
                          {pr.riskLevel} risk
                        </span>
                        <span className="text-xs text-ink-muted font-mono">
                          {pr.threadCount} thread{pr.threadCount !== 1 ? "s" : ""}
                        </span>
                        <span className="text-xs text-ink-muted font-mono">
                          {pr.state}
                        </span>
                      </div>
                    </div>
                    <span className="text-2xs text-ink-muted font-mono whitespace-nowrap">
                      {new Date(pr.updatedAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          <div className="card-brutal p-12 flex flex-col items-center justify-center gap-4">
            <div className="w-8 h-8 border-2 border-cata-cyan border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-ink-muted">Loading review data...</span>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
