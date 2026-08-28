"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "../../../components/DashboardNavigation";

const FLUTE_URL =
  process.env.NEXT_PUBLIC_FLUTE_URL || "http://localhost:8055";
const TTS_URL =
  process.env.NEXT_PUBLIC_TTS_URL || "http://localhost:7860";

interface EngineStatus {
  name: string;
  healthy: boolean;
  port: number;
  latency?: number;
}

export default function VoiceDashboardPage() {
  const [engines, setEngines] = useState<EngineStatus[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let active = true;

    const checkEngines = async () => {
      const checks: EngineStatus[] = [];

      const probe = async (name: string, url: string, port: number) => {
        const start = performance.now();
        try {
          const res = await fetch(url, {
            cache: "no-store",
            signal: AbortSignal.timeout(5000),
          });
          checks.push({
            name,
            healthy: res.ok,
            port,
            latency: Math.round(performance.now() - start),
          });
        } catch {
          checks.push({ name, healthy: false, port });
        }
      };

      await Promise.allSettled([
        probe("Flute Gateway", `${FLUTE_URL}/healthz`, 8055),
        probe(
          "Ultimate TTS",
          `${TTS_URL}/gradio_api/info`,
          7860,
        ),
      ]);

      if (active) {
        setEngines(checks);
        setLastUpdate(new Date());
        setErr(null);
      }
    };

    checkEngines();
    const interval = setInterval(checkEngines, 10000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <DashboardShell
      title="Voice Console"
      subtitle="TTS engine status, audition controls, and prosodic synthesis"
      active="voice"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Status bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="tag tag-violet">
              <span
                className={`w-2 h-2 rounded-full ${err ? "bg-cata-ember" : "bg-cata-violet animate-pulse"}`}
              />
              {err ? "Error" : "Live"}
            </span>
          </div>
          {lastUpdate && (
            <span className="text-xs text-ink-muted font-mono">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Engine status cards */}
        {engines ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {engines.map((engine) => (
              <div key={engine.name} className="card-brutal p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-display font-semibold text-sm">
                    {engine.name}
                  </h3>
                  <span
                    className={`tag ${engine.healthy ? "tag-forest" : "tag-ember"}`}
                  >
                    {engine.healthy ? "Healthy" : "Down"}
                  </span>
                </div>
                <div className="flex items-center gap-6">
                  <div className="space-y-1">
                    <span className="text-xs text-ink-muted uppercase tracking-wider font-mono">
                      Port
                    </span>
                    <div className="font-mono text-sm text-cata-cyan">
                      {engine.port}
                    </div>
                  </div>
                  {engine.latency != null && (
                    <div className="space-y-1">
                      <span className="text-xs text-ink-muted uppercase tracking-wider font-mono">
                        Latency
                      </span>
                      <div className="font-mono text-sm text-cata-gold">
                        {engine.latency}ms
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="card-brutal p-12 flex flex-col items-center justify-center gap-4">
            <div className="w-8 h-8 border-2 border-cata-violet border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-ink-muted">
              Probing voice engines...
            </span>
          </div>
        )}

        {/* Quick links */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href={FLUTE_URL}
            target="_blank"
            rel="noreferrer"
            className="card-glass p-4 group"
          >
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-sm group-hover:text-cata-violet transition-colors">
                Flute Gateway
              </span>
              <span className="font-mono text-2xs text-ink-muted">8055</span>
            </div>
            <p className="text-xs text-ink-muted mt-1">
              Prosodic synthesis &amp; WebSocket streaming
            </p>
          </a>

          <a
            href={TTS_URL}
            target="_blank"
            rel="noreferrer"
            className="card-glass p-4 group"
          >
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-sm group-hover:text-cata-violet transition-colors">
                Ultimate TTS Studio
              </span>
              <span className="font-mono text-2xs text-ink-muted">7860</span>
            </div>
            <p className="text-xs text-ink-muted mt-1">
              Multi-engine TTS with Gradio interface
            </p>
          </a>
        </div>
      </div>
    </DashboardShell>
  );
}
