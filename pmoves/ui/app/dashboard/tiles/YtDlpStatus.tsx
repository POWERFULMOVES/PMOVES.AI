"use client";
import { useEffect, useState } from "react";

type Catalog = {
  ok: boolean;
  meta?: { yt_dlp_version?: string; extractor_count?: number };
  counts?: { options: number };
};

export default function YtDlpStatus() {
  const [data, setData] = useState<Catalog | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_PMOVES_YT_BASE_URL || "http://localhost:8091";
    const supaUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    (async () => {
      try {
        const [catRes, hzRes] = await Promise.all([
          fetch(`${base}/yt/docs/catalog`),
          fetch(`${base}/healthz`),
        ]);
        const cat = (await catRes.json()) as Catalog;
        const hz = await hzRes.json();
        // merge meta when available
        if (hz && hz.provenance) {
          (cat as any).provenance = hz.provenance;
        }
        setData(cat);
      } catch (e: any) {
        setErr(String(e?.message || e));
      }
      try {
        if (supaUrl && anon) {
          const q = new URL(`${supaUrl}/rest/v1/pmoves_core.tool_docs`);
          q.searchParams.set("select", "created_at,version");
          q.searchParams.set("tool", "eq.yt-dlp");
          q.searchParams.set("doc_type", "eq.extractors");
          q.searchParams.set("order", "created_at.desc");
          q.searchParams.set("limit", "1");
          const res = await fetch(q.toString(), { headers: { apikey: anon } });
          if (res.ok) {
            const rows = (await res.json()) as Array<{ created_at: string }>;
            if (rows.length) setLastSync(rows[0].created_at);
          }
        }
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const version = data?.meta?.yt_dlp_version ?? "…";
  const extractors = data?.meta?.extractor_count ?? 0;
  const options = data?.counts?.options ?? 0;
  const provenance = (data as any)?.provenance as
    | { channel?: string; origin?: string; ytdlp_arg_version?: string; ytdlp_pip_url?: string }
    | undefined;

  return (
    <div className="rounded-md border p-4 bg-white/5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">yt-dlp Status</h3>
        {err ? (
          <span className="text-xs text-red-500">error</span>
        ) : (
          <span className="text-xs text-green-500">ok</span>
        )}
      </div>
      <div className="mt-2 text-sm">
        <div>Version: <span className="font-mono">{version}</span></div>
        <div>Extractors: <span className="font-mono">{extractors}</span></div>
        <div>Options: <span className="font-mono">{options}</span></div>
        {lastSync && (
          <div>Last Sync: <span className="font-mono">{new Date(lastSync).toLocaleString()}</span></div>
        )}
        {provenance && (provenance.channel || provenance.origin) && (
          <div className="mt-1 text-xs text-neutral-500">
            {provenance.channel && <span>Channel: <span className="font-mono">{provenance.channel}</span></span>} {" "}
            {provenance.origin && <span>Origin: <span className="font-mono">{provenance.origin}</span></span>}
          </div>
        )}
      </div>
    </div>
  );
}
