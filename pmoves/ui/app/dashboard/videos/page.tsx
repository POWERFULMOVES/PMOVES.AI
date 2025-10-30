"use client";

import { useCallback, useMemo, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
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
    <div className="p-6 space-y-6">
      <DashboardNavigation active="videos" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Videos Library</h1>
        <p className="text-sm text-neutral-600">
          Inspect Supabase <code>videos</code> rows produced by the ingestion
          workers, track approval status, and link to raw PostgREST responses for
          debugging.
        </p>
        {restUrl ? (
          <p className="text-xs text-neutral-500">
            REST endpoint preview: <a
              className="underline"
              href={`${restUrl}/videos?order=id.desc&limit=20`}
              target="_blank"
              rel="noreferrer"
            >
              {restUrl}/videos
            </a>
          </p>
        ) : (
          <p className="text-xs text-red-600">
            Configure <code>NEXT_PUBLIC_SUPABASE_REST_URL</code> for PostgREST
            links.
          </p>
        )}
      </header>

      <section className="grid gap-4 md:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Status</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded border px-2 py-1"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Namespace</span>
          <select
            value={namespaceFilter}
            onChange={(event) => setNamespaceFilter(event.target.value)}
            className="rounded border px-2 py-1"
          >
            <option value="all">All</option>
            {namespaces.map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Search title or video id</span>
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search"
            className="rounded border px-2 py-1"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Reviewer</span>
          <input
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
            placeholder="Initials or handle"
            className="rounded border px-2 py-1"
          />
        </label>
      </section>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button
          className="rounded border border-neutral-300 px-3 py-1"
          onClick={() => refresh()}
        >
          Refresh
        </button>
        <button
          className="rounded border border-neutral-300 px-3 py-1"
          onClick={handleClearFilters}
        >
          Reset filters
        </button>
        <span className="text-neutral-600">
          Showing {items.length} record{items.length === 1 ? "" : "s"}
        </span>
      </div>

      {isInitialLoading ? (
        <div className="rounded border border-dashed border-neutral-300 p-6 text-sm text-neutral-600">
          Loading videos…
        </div>
      ) : null}

      {error ? (
        <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load rows: {error.message}
        </div>
      ) : null}

      {actionError ? (
        <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {actionError}
        </div>
      ) : null}

      {actionMessage ? (
        <div className="rounded border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {actionMessage}
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-neutral-200 text-sm">
          <thead className="bg-neutral-50">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">ID</th>
              <th className="px-3 py-2 text-left font-semibold">Video</th>
              <th className="px-3 py-2 text-left font-semibold">Namespace</th>
              <th className="px-3 py-2 text-left font-semibold">Status</th>
              <th className="px-3 py-2 text-left font-semibold">Created</th>
              <th className="px-3 py-2 text-left font-semibold">Meta</th>
              <th className="px-3 py-2 text-left font-semibold">Links</th>
              <th className="px-3 py-2 text-left font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200">
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
                  <td className="px-3 py-2 text-neutral-600">
                    <div className="font-mono text-xs">{row.id}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">
                      {row.title || row.video_id || "Untitled"}
                    </div>
                    <div className="text-xs text-neutral-500">
                      {row.video_id ? `video_id: ${row.video_id}` : "no video id"}
                    </div>
                    {meta.channel?.title ? (
                      <div className="text-xs text-neutral-500">
                        channel: {meta.channel.title}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">{row.namespace || "—"}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium capitalize">{status}</div>
                    {meta.rejection_reason ? (
                      <div className="text-xs text-red-600">
                        rejected: {meta.rejection_reason}
                      </div>
                    ) : null}
                    {lastReview ? (
                      <div className="text-xs text-neutral-500">
                        last review {lastReview.status} by {lastReview.reviewer || "—"}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    <div>{formatDate(row.created_at)}</div>
                    {meta.reviewed_at ? (
                      <div className="text-xs text-neutral-500">
                        reviewed {formatDate(meta.reviewed_at)}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-xs text-neutral-600">
                    {meta.thumb ? (
                      <a
                        href={meta.thumb}
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
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
                          className="underline"
                        >
                          source
                        </a>
                      ) : null}
                      {row.s3_base_prefix ? (
                        <span className="font-mono text-[11px] text-neutral-500">
                          {row.s3_base_prefix}
                        </span>
                      ) : null}
                      {restUrl ? (
                        <a
                          href={`${restUrl}/videos?id=eq.${row.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          PostgREST row
                        </a>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-col gap-2">
                      <button
                        className="rounded bg-emerald-600 px-3 py-1 text-white"
                        disabled={pendingAction?.id === row.id}
                        onClick={() => handleAction(row, "approve")}
                      >
                        {pendingAction?.id === row.id &&
                        pendingAction.action === "approve"
                          ? "Approving…"
                          : "Approve"}
                      </button>
                      <button
                        className="rounded bg-red-600 px-3 py-1 text-white"
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
                  className="px-3 py-6 text-center text-sm text-neutral-500"
                >
                  No records match the current filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3">
        <button
          className="rounded border border-neutral-300 px-3 py-1"
          disabled={isFetchingMore || !hasMore}
          onClick={() => fetchNext()}
        >
          {isFetchingMore ? "Loading…" : hasMore ? "Load more" : "No more rows"}
        </button>
        <span className="text-xs text-neutral-500">
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
