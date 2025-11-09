"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Database } from "../lib/database.types";
import { trackUiEvent, trackUiMetric } from "../lib/metrics";
import { getBrowserSupabaseClient } from "../lib/supabaseBrowser";

interface UploadEventsTableProps {
  ownerId: string;
  limit?: number;
}

type UploadEventRow = Database["public"]["Tables"]["upload_events"]["Row"];

type ActionState = {
  message: string | null;
  error: string | null;
};

const createEmptyRows = (): UploadEventRow[] => [];

const formatBytes = (bytes: number | null) => {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "—";
  const kib = 1024;
  const mib = kib * 1024;
  if (bytes >= mib) return `${(bytes / mib).toFixed(1)} MB`;
  if (bytes >= kib) return `${(bytes / kib).toFixed(1)} KB`;
  return `${bytes} B`;
};

const formatDate = (value: string | null | undefined) => {
  if (!value) return "—";
  try {
    const date = new Date(value);
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
  } catch {
    return value;
  }
};

const statusBadgeClass = (status: string | null) => {
  const normalized = (status || "").toLowerCase();
  switch (normalized) {
    case "complete":
      return "bg-brand-forest/10 text-brand-forest border border-brand-forest/40";
    case "error":
    case "failed":
      return "bg-brand-crimson/10 text-brand-crimson border border-brand-crimson/40";
    case "uploading":
    case "persisting":
    case "queued":
    case "processing":
      return "bg-brand-sky/10 text-brand-sky border border-brand-sky/40";
    default:
      return "bg-brand-surface-muted text-brand-muted border border-brand-border";
  }
};

const deriveAgeWarning = (row: UploadEventRow) => {
  if (!row.updated_at || !row.status) {
    return false;
  }
  if (row.status.toLowerCase() === "complete") {
    return false;
  }
  const updated = new Date(row.updated_at).getTime();
  if (Number.isNaN(updated)) {
    return false;
  }
  const ageMinutes = (Date.now() - updated) / 60000;
  return ageMinutes >= 30;
};

const ingestLabel = (row: UploadEventRow) => {
  const meta = (row.meta ?? {}) as Record<string, unknown>;
  const source = typeof meta["ingest"] === "string" ? (meta["ingest"] as string) : null;
  if (source === "ui-smoke") {
    return "smoke";
  }
  if (source === "ui-dropzone") {
    return "manual";
  }
  if (typeof source === "string" && source.trim().length > 0) {
    return source;
  }
  return row.status ? row.status : "unknown";
};

export default function UploadEventsTable({ ownerId, limit = 20 }: UploadEventsTableProps) {
  const [rows, setRows] = useState<UploadEventRow[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [{ message, error: actionError }, setActionState] = useState<ActionState>({ message: null, error: null });
  const [clearing, setClearing] = useState(false);
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);

  const fetchRows = useCallback(async () => {
    if (!ownerId) {
      trackUiEvent("uploadEvents.fetch.skipped", { reason: "missing-owner" });
      setRows(createEmptyRows());
      setLoading(false);
      return;
    }
    const started = Date.now();
    setLoading(true);
    setError(null);
    const { data, error: fetchError } = await supabase
      .from("upload_events")
      .select("*")
      .eq("owner_id", ownerId)
      .order("updated_at", { ascending: false })
      .limit(limit);
    if (fetchError) {
      setError(fetchError.message || "Failed to load uploads");
      setRows(createEmptyRows());
      trackUiMetric("uploadEvents.fetch.error", {
        ownerId,
        message: fetchError.message ?? "unknown-error",
        durationMs: Date.now() - started,
      });
    } else {
      const nextRows: UploadEventRow[] = Array.isArray(data) ? (data as UploadEventRow[]) : createEmptyRows();
      setRows(nextRows);
      trackUiMetric("uploadEvents.fetch.success", {
        ownerId,
        count: nextRows.length,
        durationMs: Date.now() - started,
      });
    }
    setLoading(false);
  }, [limit, ownerId, supabase]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchRows();
    }, 0);

    return () => {
      clearTimeout(timer);
    };
  }, [fetchRows]);

  useEffect(() => {
    if (!ownerId) {
      return;
    }
    const channel = supabase
      .channel(`upload-events-${ownerId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "upload_events",
          filter: `owner_id=eq.${ownerId}`,
        },
        () => {
          // Re-fetch to keep ordering consistent across multiple mutations.
          void fetchRows();
        }
      )
      .subscribe();

    return () => {
      try {
        void channel.unsubscribe();
      } catch {}
    };
  }, [fetchRows, ownerId, supabase]);

  const handleDelete = useCallback(
    async (id: number) => {
      const started = Date.now();
      setActionState({ message: null, error: null });
      const { error: deleteError } = await supabase.from("upload_events").delete().eq("id", id);
      if (deleteError) {
        setActionState({ message: null, error: deleteError.message || "Failed to delete row" });
        trackUiMetric("uploadEvents.delete.error", {
          ownerId,
          rowId: id,
          message: deleteError.message ?? "unknown-error",
          durationMs: Date.now() - started,
        });
      } else {
        setActionState({ message: "Upload entry removed.", error: null });
        trackUiMetric("uploadEvents.delete.success", {
          ownerId,
          rowId: id,
          durationMs: Date.now() - started,
        });
        void fetchRows();
      }
    },
    [fetchRows, ownerId, supabase]
  );

  const handleClearSmoke = useCallback(async () => {
    if (!ownerId) return;
    setClearing(true);
    const started = Date.now();
    setActionState({ message: null, error: null });
    const { error: deleteError } = await supabase
      .from("upload_events")
      .delete()
      .eq("owner_id", ownerId)
      .contains("meta", { ingest: "ui-smoke" });
    if (deleteError) {
      setActionState({ message: null, error: deleteError.message || "Failed to clear smoke rows" });
      trackUiMetric("uploadEvents.clearSmoke.error", {
        ownerId,
        message: deleteError.message ?? "unknown-error",
        durationMs: Date.now() - started,
      });
    } else {
      setActionState({ message: "Cleared smoke test entries.", error: null });
      trackUiMetric("uploadEvents.clearSmoke.success", {
        ownerId,
        durationMs: Date.now() - started,
      });
    }
    setClearing(false);
  }, [ownerId, supabase]);

  const renderRow = (row: UploadEventRow) => {
    const ageWarning = deriveAgeWarning(row);
    const meta = (row.meta ?? {}) as Record<string, unknown>;
    const namespaceValue = meta["namespace"];
    const namespace = typeof namespaceValue === "string" && namespaceValue.trim().length > 0 ? namespaceValue : "—";
    const ingest = ingestLabel(row);

    return (
      <tr key={row.id} className={ageWarning ? "bg-amber-50/60" : undefined}>
        <td className="px-4 py-3">
          <div className="font-medium text-brand-ink">{row.filename || row.object_key || "(unnamed)"}</div>
          <div className="text-xs text-brand-subtle">{row.bucket}/{row.object_key}</div>
          <div className="text-xs text-brand-subtle">namespace: {namespace}</div>
        </td>
        <td className="px-4 py-3">
          <span className={`rounded px-2 py-1 text-xs font-medium ${statusBadgeClass(row.status)}`}>
            {row.status || "unknown"}
          </span>
          <div className="mt-1 text-[11px] uppercase tracking-wide text-brand-muted">{ingest}</div>
        </td>
        <td className="px-4 py-3 text-sm text-brand-ink">{row.progress !== null ? `${row.progress}%` : "—"}</td>
        <td className="px-4 py-3 text-sm text-brand-ink">{formatBytes(row.size_bytes)}</td>
        <td className="px-4 py-3 text-sm text-brand-ink">
          <div>Updated: {formatDate(row.updated_at)}</div>
          <div className="text-xs text-brand-subtle">Created: {formatDate(row.created_at)}</div>
        </td>
        <td className="px-4 py-3 text-sm">
          {row.error_message ? (
            <div className="text-xs text-brand-crimson">{row.error_message}</div>
          ) : (
            <span className="text-xs text-brand-subtle">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-right">
          <button
            className="rounded border border-brand-border px-3 py-1 text-xs font-medium text-brand-ink transition hover:border-brand-crimson hover:text-brand-crimson"
            onClick={() => handleDelete(row.id)}
          >
            Remove
          </button>
        </td>
      </tr>
    );
  };

  if (!ownerId) {
    return (
      <section className="rounded-md border border-amber-300 bg-amber-50 p-4 text-amber-800">
        <div className="font-semibold">Upload history unavailable</div>
        <p className="mt-1 text-sm">Boot user did not resolve, so recent uploads cannot be listed. Refresh after rotating the boot token.</p>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-brand-ink">Recent uploads</h2>
          <p className="text-xs text-brand-subtle">Auto-refreshes from Supabase (latest {limit}).</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            className="rounded border border-brand-border bg-brand-inverse px-3 py-1 font-medium text-brand-ink transition hover:border-brand-slate"
            onClick={() => void fetchRows()}
            disabled={loading}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
          <button
            className="rounded border border-brand-border bg-brand-inverse px-3 py-1 font-medium text-brand-crimson transition hover:border-brand-crimson"
            onClick={() => void handleClearSmoke()}
            disabled={clearing}
          >
            {clearing ? "Clearing…" : "Clear smoke"}
          </button>
        </div>
      </div>
      {message ? (
        <div className="rounded border border-brand-forest bg-brand-forest/10 p-3 text-sm text-brand-forest">{message}</div>
      ) : null}
      {actionError ? (
        <div className="rounded border border-brand-crimson bg-brand-crimson/10 p-3 text-sm text-brand-crimson">{actionError}</div>
      ) : null}
      {error ? (
        <div className="rounded border border-brand-crimson bg-brand-crimson/10 p-3 text-sm text-brand-crimson">{error}</div>
      ) : null}
      <div className="overflow-hidden rounded-lg border border-brand-border">
        <table className="min-w-full divide-y divide-brand-border text-sm">
          <thead className="bg-brand-surface-muted text-xs font-semibold uppercase text-brand-muted">
            <tr>
              <th className="px-4 py-3 text-left">File</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Progress</th>
              <th className="px-4 py-3 text-left">Size</th>
              <th className="px-4 py-3 text-left">Timestamps</th>
              <th className="px-4 py-3 text-left">Error</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border bg-brand-inverse">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-10 text-center text-sm text-brand-muted">
                  {loading ? "Loading uploads…" : "No uploads recorded yet."}
                </td>
              </tr>
            ) : (
              rows.map(renderRow)
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-brand-muted">
        Smoke runs seed placeholder rows with status <code>preparing</code>. Use the Clear smoke button once validation is finished to tidy the list.
      </p>
    </section>
  );
}
