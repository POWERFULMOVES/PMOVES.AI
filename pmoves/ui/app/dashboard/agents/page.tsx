"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardNavigation";
import type { AgentTaxonomyResponse, Agent, AgentClass, AgentType } from "@/lib/types/agents";

export default function AgentsDashboardPage() {
  const [data, setData] = useState<AgentTaxonomyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [classFilter, setClassFilter] = useState<AgentClass | "ALL">("ALL");
  const [typeFilter, setTypeFilter] = useState<AgentType | "ALL">("ALL");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"tree" | "grid">("tree");

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const res = await fetch("/api/agents/taxonomy");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
        setError(null);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };

    fetchAgents();
  }, []);

  const filteredAgents = data?.agents.filter((agent) => {
    const matchesClass = classFilter === "ALL" || agent.class === classFilter;
    const matchesType = typeFilter === "ALL" || agent.primaryType === typeFilter || agent.secondaryType === typeFilter;
    const matchesSearch =
      !search ||
      agent.name.toLowerCase().includes(search.toLowerCase()) ||
      agent.slug.toLowerCase().includes(search.toLowerCase());
    return matchesClass && matchesType && matchesSearch;
  }) || [];

  return (
    <DashboardShell
      title="Agent Taxonomy"
      subtitle={`PMOVES agent classification system • ${data?.total || 0} agents`}
      active="agents"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Class stats */}
        {data && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {(["Legendary", "Standard", "Specialized", "Utility"] as AgentClass[]).map((cls) => (
              <div
                key={cls}
                className="card-glass p-4 cursor-pointer hover:border-cata-cyan transition-colors"
                onClick={() => setClassFilter(classFilter === cls ? "ALL" : cls)}
              >
                <span className="text-xs text-ink-muted uppercase tracking-wider">{cls}</span>
                <div className="font-display font-bold text-2xl">
                  {data.byClass[cls]?.length || 0}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-ink-muted uppercase tracking-wider">Class:</label>
            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value as AgentClass | "ALL")}
              className="px-3 py-1.5 text-xs font-mono border border-border-subtle bg-void text-ink-primary focus:outline-none focus:border-cata-cyan"
            >
              <option value="ALL">All Classes</option>
              <option value="Legendary">Legendary</option>
              <option value="Standard">Standard</option>
              <option value="Specialized">Specialized</option>
              <option value="Utility">Utility</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-ink-muted uppercase tracking-wider">Type:</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as AgentType | "ALL")}
              className="px-3 py-1.5 text-xs font-mono border border-border-subtle bg-void text-ink-primary focus:outline-none focus:border-cata-cyan"
            >
              <option value="ALL">All Types</option>
              <option value="Data">Data</option>
              <option value="API">API</option>
              <option value="LLM">LLM</option>
              <option value="Worker">Worker</option>
              <option value="Media">Media</option>
              <option value="Agent">Agent</option>
              <option value="UI">UI</option>
            </select>
          </div>

          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search agents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-1.5 text-xs font-mono border border-border-subtle bg-void text-ink-primary focus:outline-none focus:border-cata-cyan"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setView("tree")}
              className={`px-3 py-1.5 text-xs font-mono border transition-all ${
                view === "tree"
                  ? "border-cata-cyan text-cata-cyan bg-cata-cyan/10"
                  : "border-border-subtle text-ink-secondary hover:border-ink-muted"
              }`}
            >
              Tree
            </button>
            <button
              onClick={() => setView("grid")}
              className={`px-3 py-1.5 text-xs font-mono border transition-all ${
                view === "grid"
                  ? "border-cata-cyan text-cata-cyan bg-cata-cyan/10"
                  : "border-border-subtle text-ink-secondary hover:border-ink-muted"
              }`}
            >
              Grid
            </button>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="card-brutal border-cata-ember">
            <div className="p-4 text-cata-ember">{error}</div>
          </div>
        )}

        {/* Agents */}
        {view === "tree" ? (
          <AgentTreeView agents={filteredAgents} />
        ) : (
          <AgentGridView agents={filteredAgents} />
        )}
      </div>
    </DashboardShell>
  );
}

function AgentTreeView({ agents }: { agents: Agent[] }) {
  // Group by class for tree view
  const grouped = agents.reduce((acc, agent) => {
    if (!acc[agent.class]) acc[agent.class] = [];
    acc[agent.class].push(agent);
    return acc;
  }, {} as Record<Agent["class"], Agent[]>);

  return (
    <div className="space-y-6">
      {(["Legendary", "Standard", "Specialized", "Utility"] as AgentClass[]).map((cls) => {
        const classAgents = grouped[cls] || [];
        if (classAgents.length === 0) return null;

        return (
          <div key={cls}>
            <h3 className="font-display font-bold text-sm text-cata-cyan mb-3 flex items-center gap-2">
              <span className="w-2 h-2 bg-cata-cyan" />
              {cls} ({classAgents.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {classAgents.map((agent) => (
                <AgentCard key={agent.slug} agent={agent} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AgentGridView({ agents }: { agents: Agent[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {agents.map((agent) => (
        <AgentCard key={agent.slug} agent={agent} compact />
      ))}
    </div>
  );
}

function AgentCard({ agent, compact = false }: { agent: Agent; compact?: boolean }) {
  const typeColor = {
    Data: "bg-amber-700",
    API: "bg-blue-600",
    LLM: "bg-red-600",
    Worker: "bg-yellow-500",
    Media: "bg-cyan-500",
    Agent: "bg-purple-600",
    UI: "bg-gray-200",
  }[agent.primaryType];

  return (
    <div className="card-glass p-4 hover:border-cata-cyan transition-colors group">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {agent.signature?.glyph && (
            <span
              className="text-lg"
              style={{ color: agent.signature.color }}
              title={agent.signature.voice}
            >
              {agent.signature.glyph}
            </span>
          )}
          <h4 className="font-display font-semibold text-sm group-hover:text-cata-cyan transition-colors">
            {agent.name}
          </h4>
        </div>
        <span className={`w-2 h-2 rounded-full ${typeColor}`} />
      </div>

      {!compact && (
        <>
          <p className="text-xs text-ink-muted mb-2">{agent.slug}</p>

          <div className="flex flex-wrap gap-1 mb-3">
            <span className="text-2xs px-2 py-0.5 bg-void-elevated border border-border-subtle">
              {agent.class}
            </span>
            <span className="text-2xs px-2 py-0.5 bg-void-elevated border border-border-subtle">
              {agent.primaryType}
            </span>
            <span className="text-2xs px-2 py-0.5 bg-void-elevated border border-border-subtle">
              {agent.evolutionStage}
            </span>
          </div>

          {agent.healthCheck && (
            <a
              href={agent.healthCheck}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-cata-forest hover:underline"
            >
              Health Check
            </a>
          )}
        </>
      )}

      {compact && agent.healthCheck && (
        <div className="flex gap-2 mt-2">
          <a
            href={agent.healthCheck}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-cata-forest hover:underline"
          >
            Health
          </a>
        </div>
      )}
    </div>
  );
}
