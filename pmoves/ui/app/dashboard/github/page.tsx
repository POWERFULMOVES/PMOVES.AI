"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardNavigation";
import type { PRListResponse, PRStatus, PRState } from "@/lib/types/github";

export default function GitHubDashboardPage() {
  const [data, setData] = useState<PRListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<PRState | "ALL">("ALL");
  const [search, setSearch] = useState("");

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const fetchPRs = async () => {
      try {
        const res = await fetch("/api/github/prs", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
        setError(null);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };

    fetchPRs();
    const interval = setInterval(fetchPRs, 30000);
    return () => clearInterval(interval);
  }, []);

  const filteredItems = data?.items.filter((pr) => {
    const matchesFilter = filter === "ALL" || pr.state === filter;
    const matchesSearch =
      !search ||
      pr.title.toLowerCase().includes(search.toLowerCase()) ||
      pr.author.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  }) || [];

  return (
    <DashboardShell
      title="GitHub Pull Requests"
      subtitle={`POWERFULMOVES repository PR status • ${data?.total || 0} total`}
      active="github"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Stats bar */}
        {data && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Total</span>
              <div className="font-display font-bold text-2xl text-cata-cyan">{data.total}</div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Open</span>
              <div className="font-display font-bold text-2xl text-cata-forest">{data.open}</div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Merged</span>
              <div className="font-display font-bold text-2xl text-cata-violet">{data.merged}</div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Closed</span>
              <div className="font-display font-bold text-2xl text-cata-ember">{data.closed}</div>
            </div>
            <div className="card-glass p-4">
              <span className="text-xs text-ink-muted uppercase tracking-wider">Draft</span>
              <div className="font-display font-bold text-2xl text-ink-muted">{data.draft}</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-ink-muted uppercase tracking-wider">State:</label>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as PRState | "ALL")}
              className="px-3 py-1.5 text-xs font-mono border border-border-subtle bg-void text-ink-primary focus:outline-none focus:border-cata-cyan"
            >
              <option value="ALL">All States</option>
              <option value="OPEN">Open</option>
              <option value="DRAFT">Draft</option>
              <option value="MERGED">Merged</option>
              <option value="CLOSED">Closed</option>
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search by title or author..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-1.5 text-xs font-mono border border-border-subtle bg-void text-ink-primary focus:outline-none focus:border-cata-cyan"
            />
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="card-brutal border-cata-ember">
            <div className="p-4 flex items-center gap-4">
              <div className="w-8 h-8 flex items-center justify-center bg-cata-ember/20 text-cata-ember font-display font-bold">
                !
              </div>
              <div>
                <h3 className="font-display font-semibold text-cata-ember">Failed to load PRs</h3>
                <p className="text-sm text-ink-secondary">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* PR List */}
        <div className="card-brutal">
          {filteredItems.length === 0 ? (
            <div className="p-12 text-center text-ink-muted">
              {data ? "No pull requests match your filters" : "Loading..."}
            </div>
          ) : (
            <div className="divide-y divide-border-subtle">
              {filteredItems.map((pr) => (
                <PRRow key={pr.number} pr={pr} />
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}

function PRRow({ pr }: { pr: PRStatus }) {
  const stateColor = {
    OPEN: "text-cata-forest bg-cata-forest/10",
    MERGED: "text-cata-violet bg-cata-violet/10",
    CLOSED: "text-cata-ember bg-cata-ember/10",
    DRAFT: "text-ink-muted bg-void-elevated",
  }[pr.state] || "text-ink-muted";

  return (
    <div className="p-4 hover:bg-void-elevated transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <a
              href={pr.url}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-sm text-cata-cyan hover:underline"
            >
              #{pr.number}
            </a>
            <span className={`text-2xs px-2 py-0.5 uppercase tracking-wider ${stateColor}`}>
              {pr.state.toLowerCase()}
            </span>
            {pr.labels.length > 0 && (
              <div className="flex gap-1">
                {pr.labels.map((label) => (
                  <span
                    key={label}
                    className="text-2xs px-2 py-0.5 bg-void-elevated border border-border-subtle text-ink-muted"
                  >
                    {label}
                  </span>
                ))}
              </div>
            )}
          </div>
          <h3 className="font-display font-semibold text-sm mt-2">{pr.title}</h3>
          <p className="text-xs text-ink-muted mt-1">
            <span className="font-mono">{pr.author}</span>
            {" • "}
            <span>Opened {new Date(pr.createdAt).toLocaleDateString()}</span>
            {pr.updatedAt !== pr.createdAt && (
              <span> • Updated {new Date(pr.updatedAt).toLocaleDateString()}</span>
            )}
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-ink-muted">
            <span className="text-cata-forest">+{pr.additions}</span>
            {" "}
            <span className="text-cata-ember">-{pr.deletions}</span>
          </div>
          <div className="text-xs text-ink-muted mt-1">
            {pr.changedFiles} files
          </div>
        </div>
      </div>
    </div>
  );
}
