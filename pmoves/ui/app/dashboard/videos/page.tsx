"use client";

import { useCallback, useMemo, useState } from "react";
import useInfiniteSupabaseQuery from "../../../hooks/useInfiniteSupabaseQuery";
import {
  getSupabaseBrowserClient,
  getSupabaseRestUrl,
} from "../../../lib/supabaseClient";

interface VideoRowMeta {
  [key: string]: any;
  approval_status?: string | null;
  approval_history?: Array<{
    status: string;
    reviewer?: string | null;
    note?: string | null;
    at: string;
  }>;
  rejection_reason?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  thumb?: string | null;
  channel?: {
    title?: string | null;
    id?: string | null;
  } | null;
}

interface VideoRow {
  id: number;
  video_id: string | null;
  namespace: string | null;
  title: string | null;
  source_url: string | null;
  s3_base_prefix: string | null;
  created_at: string;
  meta: VideoRowMeta | null;
}

type VideoAction = "approve" | "reject";

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "needs-review", label: "Needs review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "published", label: "Published" },
];

const formatDate = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
};

const isObject = (value: unknown): value is Record<string, any> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const mergeMeta = (
  current: VideoRowMeta | null | undefined,
  patch: Record<string, unknown>
): VideoRowMeta => {
  const base = isObject(current) ? current : {};
  const merged: Record<string, unknown> = { ...base, ...patch };
  return Object.fromEntries(
    Object.entries(merged).filter(([, v]) => v !== undefined)
  ) as VideoRowMeta;
};

export default function VideosDashboardPage() {
  const client = useMemo(() => getSupabaseBrowserClient(), []);
  const restUrl = useMemo(() => getSupabaseRestUrl(), []);

  const [statusFilter, setStatusFilter] = useState<string>("needs-review");
  const [namespaceFilter, setNamespaceFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [reviewer, setReviewer] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<
    { id: number; action: VideoAction } | null
  >(null);

  const filters = useCallback(
    (query: any) => {
      let builder = query;
      if (namespaceFilter && namespaceFilter !== "all") {
        builder = builder.eq("namespace", namespaceFilter);
      }
      if (statusFilter && statusFilter !== "all") {
        if (statusFilter === "needs-review") {
          builder = builder.or(
            "meta->>approval_status.is.null,meta->>approval_status.eq.pending"
          );
        } else {
          builder = builder.filter(
            "meta->>approval_status",
            "eq",
            statusFilter
          );
        }
      }
      const trimmed = searchTerm.trim();
      if (trimmed) {
        if (/^[A-Za-z0-9_-]{6,}$/.test(trimmed)) {
          builder = builder.eq("video_id", trimmed);
        } else {
          builder = builder.ilike("title", `%${trimmed}%`);
        }
      }
      return builder;
    },
    [namespaceFilter, searchTerm, statusFilter]
  );

  const {
    items,
    fetchNext,
    refresh,
    hasMore,
    isFetchingMore,
    isInitialLoading,
    error,
  } = useInfiniteSupabaseQuery<VideoRow>({
    client,
    table: "videos",
    select:
      "id,video_id,namespace,title,source_url,s3_base_prefix,created_at,meta",
    pageSize: 20,
    cursorColumn: "id",
    order: { column: "id", ascending: false },
    filters,
  });

  const namespaces = useMemo(() => {
    const set = new Set<string>();
    items.forEach((row) => {
      if (row.namespace) {
        set.add(row.namespace);
      }
    });
    return Array.from(set).sort();
  }, [items]);

  const handleAction = useCallback(
    async (row: VideoRow, action: VideoAction) => {
      setPendingAction({ id: row.id, action });
      setActionError(null);
      setActionMessage(null);

      try {
        const now = new Date().toISOString();
        const meta = isObject(row.meta) ? row.meta : {};
        const history: VideoRowMeta["approval_history"] = Array.isArray(
          meta.approval_history
        )
          ? [...meta.approval_history]
          : [];

        let rejectionReason: string | null | undefined = undefined;
        let note: string | null = null;

        if (action === "reject") {
          const reason = window.prompt(
            "Provide a rejection note (optional)",
            meta.rejection_reason || ""
          );
          if (reason === null) {
            setPendingAction(null);
            return;
          }
          rejectionReason = reason || null;
          note = rejectionReason;
        }

        if (action === "approve") {
          rejectionReason = null;
        }

        history.push({
          status: action === "approve" ? "approved" : "rejected",
          reviewer: reviewer || null,
          note,
          at: now,
        });

        const updatedMeta = mergeMeta(meta, {
          approval_status: action === "approve" ? "approved" : "rejected",
          approval_history: history,
          rejection_reason: rejectionReason,
          reviewed_at: now,
          reviewed_by: reviewer || null,
        });

        const { error: mutationError } = await client
          .from("videos")
          .update({ meta: updatedMeta })
          .eq("id", row.id)
          .select("id")
          .single();

        if (mutationError) {
          throw mutationError;
        }

        setActionMessage(
          `Video ${row.video_id || row.id} ${
            action === "approve" ? "approved" : "rejected"
          }.`
        );
        await refresh();
      } catch (mutationErr: any) {
        setActionError(mutationErr?.message || String(mutationErr));
      } finally {
        setPendingAction(null);
      }
    },
    [client, refresh, reviewer]
  );

  const handleClearFilters = useCallback(() => {
    setStatusFilter("needs-review");
    setNamespaceFilter("all");
    setSearchTerm("");
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-brand-ink">Videos Signal Vault</h1>
        <p className="text-sm text-brand-muted">
          Keep the cooperative empowerment story in motion—DARKXSIDE trusts this vault to surface the clips that rally each crew.
          {' '}Run the{' '}
          <a
            className="font-medium text-brand-sky underline underline-offset-4 hover:text-brand-gold"
            href="https://github.com/Cataclysm-Studios-Inc/PMOVES.AI/blob/main/pmoves/docs/SMOKETESTS.md#L143"
            target="_blank"
            rel="noreferrer"
          >
            ingestion smoke checks
          </a>{' '}
          whenever approvals shift so Supabase and MinIO stay in sync.
        </p>
        {restUrl ? (
          <p className="text-xs text-brand-subtle">
            REST endpoint preview:{' '}
            <a
              className="font-medium text-brand-sky underline underline-offset-4 hover:text-brand-gold"
              href={`${restUrl}/videos?order=id.desc&limit=20`}
              target="_blank"
              rel="noreferrer"
            >
              {restUrl}/videos
            </a>
          </p>
        ) : (
          <p className="text-xs text-brand-crimson">
            Configure <code>NEXT_PUBLIC_SUPABASE_REST_URL</code> for PostgREST
            links.
          </p>
        )}
      </header>

      <section className="grid gap-4 md:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm text-brand-ink">
          <span className="font-medium text-brand-ink">Status</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded border border-brand-border bg-brand-inverse px-2 py-1 text-brand-ink"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-brand-ink">
          <span className="font-medium text-brand-ink">Namespace</span>
          <select
            value={namespaceFilter}
            onChange={(event) => setNamespaceFilter(event.target.value)}
            className="rounded border border-brand-border bg-brand-inverse px-2 py-1 text-brand-ink"
          >
            <option value="all">All</option>
            {namespaces.map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-brand-ink">
          <span className="font-medium text-brand-ink">Search title or video id</span>
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search"
            className="rounded border border-brand-border bg-brand-inverse px-2 py-1 text-brand-ink placeholder:text-brand-subtle"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-brand-ink">
          <span className="font-medium text-brand-ink">Reviewer</span>
          <input
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
            placeholder="Initials or handle"
            className="rounded border border-brand-border bg-brand-inverse px-2 py-1 text-brand-ink placeholder:text-brand-subtle"
          />
        </label>
      </section>

      <div className="flex flex-wrap items-center gap-3 text-sm text-brand-ink">
        <button
          className="rounded border border-brand-border bg-brand-inverse px-3 py-1 font-medium text-brand-ink transition hover:border-brand-slate hover:text-brand-ink-strong"
          onClick={() => refresh()}
        >
          Refresh
        </button>
        <button
          className="rounded border border-brand-border bg-brand-inverse px-3 py-1 font-medium text-brand-ink transition hover:border-brand-slate hover:text-brand-ink-strong"
          onClick={handleClearFilters}
        >
          Reset filters
        </button>
        <span className="text-brand-muted">
          Showing {items.length} record{items.length === 1 ? "" : "s"}
        </span>
      </div>

      {isInitialLoading ? (
        <div className="rounded border border-dashed border-brand-border p-6 text-sm text-brand-muted">
          Loading videos…
        </div>
      ) : null}

      {error ? (
        <div className="rounded border border-brand-crimson bg-[rgba(219,69,69,0.08)] p-4 text-sm text-brand-crimson">
          Failed to load rows: {error.message}
        </div>
      ) : null}

      {actionError ? (
        <div className="rounded border border-brand-crimson bg-[rgba(219,69,69,0.08)] p-4 text-sm text-brand-crimson">
          {actionError}
        </div>
      ) : null}

      {actionMessage ? (
        <div className="rounded border border-brand-forest bg-[rgba(46,139,87,0.12)] p-4 text-sm text-brand-forest">
          {actionMessage}
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-brand-border text-sm">
          <thead className="bg-brand-surface-muted">
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-brand-muted">
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Video</th>
              <th className="px-3 py-2">Namespace</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2">Meta</th>
              <th className="px-3 py-2">Links</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-border bg-brand-inverse text-brand-ink">
            {items.map((row) => {
              const meta = isObject(row.meta) ? row.meta : {};
              const status = meta.approval_status || "pending";
              const history = Array.isArray(meta.approval_history)
                ? meta.approval_history
                : [];
              const lastReview = history.length
                ? history[history.length - 1]
                : null;
              return (
                <tr key={row.id} className="align-top">
                  <td className="px-3 py-2 text-brand-subtle">
                    <div className="font-mono text-xs text-brand-muted">{row.id}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-brand-ink-strong">
                      {row.title || row.video_id || "Untitled"}
                    </div>
                    <div className="text-xs text-brand-subtle">
                      {row.video_id ? `video_id: ${row.video_id}` : "no video id"}
                    </div>
                    {meta.channel?.title ? (
                      <div className="text-xs text-brand-subtle">
                        channel: {meta.channel.title}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-brand-ink">{row.namespace || "—"}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium capitalize text-brand-ink">{status}</div>
                    {meta.rejection_reason ? (
                      <div className="text-xs text-brand-crimson">
                        rejected: {meta.rejection_reason}
                      </div>
                    ) : null}
                    {lastReview ? (
                      <div className="text-xs text-brand-subtle">
                        last review {lastReview.status} by {lastReview.reviewer || "—"}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    <div className="text-brand-ink">{formatDate(row.created_at)}</div>
                    {meta.reviewed_at ? (
                      <div className="text-xs text-brand-subtle">
                        reviewed {formatDate(meta.reviewed_at)}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-xs text-brand-muted">
                    {meta.thumb ? (
                      <a
                        href={meta.thumb}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-brand-sky underline underline-offset-4 hover:text-brand-gold"
                      >
                        preview thumb
                      </a>
                    ) : null}
                    {meta.duration ? <div>duration: {meta.duration}s</div> : null}
                    {meta.statistics?.view_count ? (
                      <div>views: {meta.statistics.view_count}</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    <div className="flex flex-col gap-1">
                      {row.source_url ? (
                        <a
                          href={row.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-brand-sky underline underline-offset-4 hover:text-brand-gold"
                        >
                          source
                        </a>
                      ) : null}
                      {row.s3_base_prefix ? (
                        <span className="font-mono text-[11px] text-brand-subtle">
                          {row.s3_base_prefix}
                        </span>
                      ) : null}
                      {restUrl ? (
                        <a
                          href={`${restUrl}/videos?id=eq.${row.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-brand-sky underline underline-offset-4 hover:text-brand-gold"
                        >
                          PostgREST row
                        </a>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-col gap-2">
                      <button
                        className="rounded bg-brand-forest px-3 py-1 text-brand-inverse transition hover:bg-brand-sky hover:text-brand-ink-strong"
                        disabled={pendingAction?.id === row.id}
                        onClick={() => handleAction(row, "approve")}
                      >
                        {pendingAction?.id === row.id &&
                        pendingAction.action === "approve"
                          ? "Approving…"
                          : "Approve"}
                      </button>
                      <button
                        className="rounded bg-brand-crimson px-3 py-1 text-brand-inverse transition hover:bg-brand-rust"
                        disabled={pendingAction?.id === row.id}
                        onClick={() => handleAction(row, "reject")}
                      >
                        {pendingAction?.id === row.id &&
                        pendingAction.action === "reject"
                          ? "Rejecting…"
                          : "Reject"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && !isInitialLoading ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-3 py-6 text-center text-sm text-brand-muted"
                >
                  No records match the current filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3 text-brand-ink">
        <button
          className="rounded border border-brand-border bg-brand-inverse px-3 py-1 font-medium text-brand-ink transition hover:border-brand-slate hover:text-brand-ink-strong disabled:opacity-60"
          disabled={isFetchingMore || !hasMore}
          onClick={() => fetchNext()}
        >
          {isFetchingMore ? "Loading…" : hasMore ? "Load more" : "No more rows"}
        </button>
        <span className="text-xs text-brand-subtle">
          Cursor: {cursorSummary(items)}
        </span>
      </div>
    </div>
  );
}

function cursorSummary(rows: VideoRow[]): string {
  if (!rows.length) {
    return "—";
  }
  const last = rows[rows.length - 1];
  return `id<=${last.id}`;
}
