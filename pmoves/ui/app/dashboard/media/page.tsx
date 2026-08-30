"use client";

import { useEffect, useState } from "react";
import { DashboardShell } from "../../../components/DashboardNavigation";

interface PipelineService {
  name: string;
  url: string;
  port: number;
  healthy: boolean;
  latency?: number;
}

const PIPELINE_SERVICES = [
  { name: "PMOVES.YT", healthUrl: "/api/health", port: 8077 },
  { name: "FFmpeg-Whisper", healthUrl: "/api/health", port: 8078 },
  { name: "Video Analyzer", healthUrl: "/api/health", port: 8079 },
  { name: "Audio Analyzer", healthUrl: "/api/health", port: 8082 },
  { name: "Extract Worker", healthUrl: "/api/health", port: 8083 },
];

export default function MediaDashboardPage() {
  const [services, setServices] = useState<PipelineService[] | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let active = true;

    const checkPipeline = async () => {
      const results = await Promise.all(
        PIPELINE_SERVICES.map(async (svc) => {
          const url = `http://localhost:${svc.port}`;
          const start = performance.now();
          try {
            const res = await fetch(`${url}${svc.healthUrl}`, {
              cache: "no-store",
              signal: AbortSignal.timeout(5000),
            });
            return {
              name: svc.name,
              url,
              port: svc.port,
              healthy: res.ok,
              latency: Math.round(performance.now() - start),
            };
          } catch {
            return { name: svc.name, url, port: svc.port, healthy: false };
          }
        }),
      );

      if (active) {
        setServices(results);
        setLastUpdate(new Date());
      }
    };

    checkPipeline();
    const interval = setInterval(checkPipeline, 10000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const healthyCount = services?.filter((s) => s.healthy).length ?? 0;
  const totalCount = services?.length ?? 0;

  return (
    <DashboardShell
      title="Media Pipeline"
      subtitle="Pipeline health, artifact preview, and render status"
      active="media"
    >
      <div className="p-6 lg:p-8 space-y-6">
        {/* Status bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="tag tag-ember">
              <span
                className={`w-2 h-2 rounded-full ${
                  healthyCount === totalCount && totalCount > 0
                    ? "bg-cata-forest animate-pulse"
                    : "bg-cata-ember animate-pulse"
                }`}
              />
              {healthyCount}/{totalCount} Healthy
            </span>
          </div>
          {lastUpdate && (
            <span className="text-xs text-ink-muted font-mono">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Pipeline service grid */}
        {services ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {services.map((svc) => (
              <div key={svc.name} className="card-brutal p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-display font-semibold text-sm">
                    {svc.name}
                  </h3>
                  <span
                    className={`tag ${svc.healthy ? "tag-forest" : "tag-ember"}`}
                  >
                    {svc.healthy ? "Up" : "Down"}
                  </span>
                </div>
                <div className="flex items-center gap-6">
                  <div className="space-y-1">
                    <span className="text-xs text-ink-muted uppercase tracking-wider font-mono">
                      Port
                    </span>
                    <div className="font-mono text-sm text-cata-cyan">
                      {svc.port}
                    </div>
                  </div>
                  {svc.latency != null && (
                    <div className="space-y-1">
                      <span className="text-xs text-ink-muted uppercase tracking-wider font-mono">
                        Latency
                      </span>
                      <div className="font-mono text-sm text-cata-gold">
                        {svc.latency}ms
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="card-brutal p-12 flex flex-col items-center justify-center gap-4">
            <div className="w-8 h-8 border-2 border-cata-ember border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-ink-muted">
              Probing media pipeline...
            </span>
          </div>
        )}

        {/* Pipeline flow diagram */}
        <div className="card-glass p-6">
          <h3 className="font-display font-semibold text-sm mb-4">
            Pipeline Flow
          </h3>
          <div className="flex items-center gap-2 overflow-x-auto text-xs font-mono">
            <span className="tag tag-cyan">Ingest</span>
            <span className="text-ink-muted">&rarr;</span>
            <span className="tag tag-violet">Transcribe</span>
            <span className="text-ink-muted">&rarr;</span>
            <span className="tag tag-gold">Analyze</span>
            <span className="text-ink-muted">&rarr;</span>
            <span className="tag tag-forest">Index</span>
            <span className="text-ink-muted">&rarr;</span>
            <span className="tag tag-ember">Render</span>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
