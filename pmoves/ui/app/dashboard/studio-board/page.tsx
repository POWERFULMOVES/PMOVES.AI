"use client";

import { useCallback, useMemo, useState } from "react";
import useInfiniteSupabaseQuery from "../../../hooks/useInfiniteSupabaseQuery";
import {
  getSupabaseBrowserClient,
  getSupabaseRestUrl,
} from "../../../lib/supabaseClient";

interface StudioBoardRowMeta {
  [key: string]: any;
  review_history?: Array<{
    status: string;
    reviewer?: string | null;
    note?: string | null;
    at: string;
  }>;
  rejection_reason?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  publish_event_sent_at?: string | null;
  tags?: string[];
  persona?: string;
  workflow?: string;
}

interface StudioBoardRow {
  id: number;
  title: string | null;
  namespace: string | null;
  status: string | null;
  content_url: string | null;
  created_at: string;
  meta: StudioBoardRowMeta | null;
}

type ReviewAction = "approve" | "reject";

const STATUS_OPTIONS = ["all", "submitted", "approved", "rejected", "published"];

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
  current: StudioBoardRowMeta | null | undefined,
  patch: Record<string, unknown>
): StudioBoardRowMeta => {
  const base = isObject(current) ? current : {};
  const merged: Record<string, unknown> = { ...base, ...patch };
  return Object.fromEntries(
    Object.entries(merged).filter(([, v]) => v !== undefined)
  ) as StudioBoardRowMeta;
};

export default function StudioBoardDashboardPage(): JSX.Element {
  const client = useMemo(() => getSupabaseBrowserClient(), []);
  const restUrl = useMemo(() => getSupabaseRestUrl(), []);

  const [statusFilter, setStatusFilter] = useState<string>("submitted");
  const [namespaceFilter, setNamespaceFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [reviewer, setReviewer] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<
    { id: number; action: ReviewAction } | null
  >(null);

  const filters = useCallback(
    (query: any) => {
      let builder = query;
      if (statusFilter && statusFilter !== "all") {
        builder = builder.eq("status", statusFilter);
      }
      if (namespaceFilter && namespaceFilter !== "all") {
        builder = builder.eq("namespace", namespaceFilter);
      }
      if (searchTerm.trim()) {
        builder = builder.ilike("title", `%${searchTerm.trim()}%`);
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
  } = useInfiniteSupabaseQuery<StudioBoardRow>({
    client,
    table: "studio_board",
    select:
      "id,title,namespace,status,content_url,created_at,meta",
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
    async (row: StudioBoardRow, action: ReviewAction) => {
      setPendingAction({ id: row.id, action });
      setActionError(null);
      setActionMessage(null);

      try {
        const now = new Date().toISOString();
        const meta = isObject(row.meta) ? row.meta : {};
        const history: StudioBoardRowMeta["review_history"] = Array.isArray(
          meta.review_history
        )
          ? [...meta.review_history]
          : [];

        let rejectionReason: string | null | undefined = undefined;
        let note: string | null = null;

        if (action === "reject") {
          const userReason = window.prompt(
            "Provide a short rejection reason (optional)",
            meta.rejection_reason || ""
          );
          if (userReason === null) {
            setPendingAction(null);
            return;
          }
          rejectionReason = userReason || null;
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
          review_history: history,
          reviewed_at: now,
          reviewed_by: reviewer || null,
          rejection_reason: rejectionReason,
        });

        const payload: Partial<StudioBoardRow> = {
          status: action === "approve" ? "approved" : "rejected",
          meta: updatedMeta,
        };

        const { error: mutationError } = await client
          .from("studio_board")
          .update(payload)
          .eq("id", row.id)
          .select("id")
          .single();

        if (mutationError) {
          throw mutationError;
        }

        setActionMessage(
          `Row ${row.id} ${action === "approve" ? "approved" : "rejected"}.`
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
    setStatusFilter("submitted");
    setNamespaceFilter("all");
    setSearchTerm("");
    void refresh();
  }, [refresh]);

  return (
    <div className="p-6 space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Studio Board Approvals</h1>
        <p className="text-sm text-neutral-600">
          Review Supabase <code>studio_board</code> submissions, approve or
          reject them inline, and jump to PostgREST for deeper debugging when
          needed.
        </p>
        {restUrl ? (
          <p className="text-xs text-neutral-500">
            REST endpoint preview: <a
              className="underline"
              href={`${restUrl}/studio_board?order=id.desc&limit=20`}
              target="_blank"
              rel="noreferrer"
            >
              {restUrl}/studio_board
            </a>
          </p>
        ) : (
          <p className="text-xs text-red-600">
            Configure <code>NEXT_PUBLIC_SUPABASE_REST_URL</code> to enable
            deep-linking into PostgREST queries.
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
              <option key={option} value={option}>
                {option === "all" ? "All" : option}
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
          <span className="font-medium">Search title</span>
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search by title"
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
          Loading studio board records…
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
              <th className="px-3 py-2 text-left font-semibold">Title</th>
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
              const history = Array.isArray(meta.review_history)
                ? meta.review_history
                : [];
              const lastReview = history.length > 0 ? history[history.length - 1] : null;
              return (
                <tr key={row.id} className="align-top">
                  <td className="px-3 py-2 text-neutral-600">
                    <div className="font-mono text-xs">{row.id}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{row.title || "Untitled"}</div>
                    {meta.tags && Array.isArray(meta.tags) && meta.tags.length ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {meta.tags.map((tag: string) => (
                          <span
                            key={tag}
                            className="rounded bg-neutral-200 px-2 py-0.5 text-[10px] uppercase tracking-wide"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    {row.namespace || "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium capitalize">
                      {row.status || "unknown"}
                    </div>
                    {meta.publish_event_sent_at ? (
                      <div className="text-xs text-neutral-500">
                        published @ {formatDate(meta.publish_event_sent_at)}
                      </div>
                    ) : null}
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
                    {meta.persona ? <div>persona: {meta.persona}</div> : null}
                    {meta.workflow ? <div>workflow: {meta.workflow}</div> : null}
                    {meta.source ? <div>source: {meta.source}</div> : null}
                    {meta.job_id ? <div>job: {meta.job_id}</div> : null}
                    {meta.notes ? <div>notes: {meta.notes}</div> : null}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    <div className="flex flex-col gap-1">
                      {row.content_url ? (
                        <a
                          href={row.content_url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          asset
                        </a>
                      ) : null}
                      {restUrl ? (
                        <a
                          href={`${restUrl}/studio_board?id=eq.${row.id}`}
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

function cursorSummary(rows: StudioBoardRow[]): string {
  if (!rows.length) {
    return "—";
  }
  const last = rows[rows.length - 1];
  return `id<=${last.id}`;
}
