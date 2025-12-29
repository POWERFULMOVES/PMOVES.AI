"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";

// Helper function to join className strings (avoids template literals for Turbopack compatibility)
function cn(...classes: (string | undefined | false)[]): string {
  return classes.filter(Boolean).join(' ');
}
import {
  BulkApprovalActions,
  BulkSelectionCheckbox,
} from "../../../components/ingestion/BulkApprovalActions";
import {
  ApprovalRulesConfig,
  type ApprovalRule,
} from "../../../components/ingestion/ApprovalRulesConfig";
import {
  getSupabaseRealtimeClient,
  subscribeToIngestionQueue,
  fetchIngestionQueue,
  approveIngestion,
  rejectIngestion,
  type IngestionQueueItem,
  type IngestionStatus,
  type IngestionSourceType,
} from "../../../lib/realtimeClient";
import { formatTimeAgo } from "@/lib/timeUtils";
import { AlertBanner } from "@/components/common";

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

const SOURCE_TYPE_ICONS: Record<IngestionSourceType, string> = {
  youtube: '🎬',
  pdf: '📄',
  url: '🔗',
  upload: '📁',
  notebook: '📓',
  discord: '💬',
  telegram: '✈️',
  rss: '📡',
};

const STATUS_COLORS: Record<IngestionStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-blue-100 text-blue-800',
  rejected: 'bg-red-100 text-red-800',
  processing: 'bg-purple-100 text-purple-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '--:--';
  if (seconds === 0) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return mins + ':' + secs.toString().padStart(2, '0');
}

export default function IngestionQueuePage() {
  const [items, setItems] = useState<IngestionQueueItem[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [filter, setFilter] = useState<IngestionStatus | 'all'>('pending');
  const [sourceFilter, setSourceFilter] = useState<IngestionSourceType | 'all'>('all');
  const [processing, setProcessing] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [rules, setRules] = useState<ApprovalRule[]>([]);
  const [showRules, setShowRules] = useState(false);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ pending: number; approved: number; processing: number; completed: number }>({
    pending: 0,
    approved: 0,
    processing: 0,
    completed: 0,
  });

  // Fetch items and setup realtime
  useEffect(() => {
    let isMounted = true;
    setStatus('connecting');

    const setup = async () => {
      try {
        const client = getSupabaseRealtimeClient();

        // Fetch initial items
        const data = await fetchIngestionQueue(client, {
          status: filter === 'all' ? undefined : filter,
          sourceType: sourceFilter === 'all' ? undefined : sourceFilter,
          limit: 50,
        });

        if (isMounted) {
          // Defensive: ensure data is always an array
          setItems(Array.isArray(data) ? data : []);

          // Calculate stats
          const allItems = await fetchIngestionQueue(client, { limit: 1000 });
          // Defensive: ensure allItems is always an array before reduce
          const safeAllItems = Array.isArray(allItems) ? allItems : [];
          const statsMap = safeAllItems.reduce((acc, item) => {
            acc[item.status] = (acc[item.status] || 0) + 1;
            return acc;
          }, {} as Record<string, number>);

          setStats({
            pending: statsMap.pending || 0,
            approved: statsMap.approved || 0,
            processing: statsMap.processing || 0,
            completed: statsMap.completed || 0,
          });
        }

        // Subscribe to realtime changes
        const channel = subscribeToIngestionQueue(client, {
          onInsert: (item) => {
            if (isMounted && item && item.id) {
              setItems((prev) => {
                // Defensive: ensure prev is always an array
                const safePrev = Array.isArray(prev) ? prev : [];
                if (safePrev.some((i) => i.id === item.id)) return safePrev;
                // Add to list if matches filter
                if (filter !== 'all' && item.status !== filter) return safePrev;
                if (sourceFilter !== 'all' && item.source_type !== sourceFilter) return safePrev;
                return [item, ...safePrev];
              });
              setStats((prev) => ({
                ...prev,
                [item.status]: (prev[item.status as keyof typeof prev] || 0) + 1,
              }));
            }
          },
          onUpdate: (item) => {
            if (isMounted && item && item.id) {
              setItems((prev) => {
                // Defensive: ensure prev is always an array
                const safePrev = Array.isArray(prev) ? prev : [];
                // If item no longer matches filter, remove it
                if (filter !== 'all' && item.status !== filter) {
                  return safePrev.filter((i) => i.id !== item.id);
                }
                return safePrev.map((i) => (i.id === item.id ? item : i));
              });
            }
          },
          onDelete: (item) => {
            if (isMounted && item && item.id) {
              setItems((prev) => {
                // Defensive: ensure prev is always an array
                const safePrev = Array.isArray(prev) ? prev : [];
                return safePrev.filter((i) => i.id !== item.id);
              });
            }
          },
        });

        setStatus('connected');

        return () => {
          client.removeChannel(channel);
        };
      } catch (error) {
        console.error('Failed to setup ingestion queue:', error);
        if (isMounted) {
          setStatus('error');
        }
      }
    };

    setup();

    return () => {
      isMounted = false;
    };
  }, [filter, sourceFilter]);

  const handleApprove = useCallback(async (id: string, priority?: number) => {
    setProcessing((prev) => new Set(prev).add(id));
    try {
      const client = getSupabaseRealtimeClient();
      await approveIngestion(client, id, priority);
      // Realtime will update the list
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to approve item';
      setError('Failed to approve: ' + message);
      setTimeout(() => setError(null), 5000);
    } finally {
      setProcessing((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, []);

  const handleReject = useCallback(async (id: string, reason?: string) => {
    setProcessing((prev) => new Set(prev).add(id));
    try {
      const client = getSupabaseRealtimeClient();
      await rejectIngestion(client, id, reason);
      // Realtime will update the list
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to reject item';
      setError('Failed to reject: ' + message);
      setTimeout(() => setError(null), 5000);
    } finally {
      setProcessing((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, []);

  const handleApproveAll = useCallback(async () => {
    const pendingItems = items.filter((i) => i.status === 'pending');
    for (const item of pendingItems) {
      await handleApprove(item.id);
    }
  }, [items, handleApprove]);

  // Bulk actions
  const handleBulkApprove = useCallback(async (ids: string[], options?: { priority?: number }) => {
    setBulkProcessing(true);
    setError(null);
    try {
      const client = getSupabaseRealtimeClient();
      for (const id of ids) {
        await approveIngestion(client, id, options?.priority);
      }
      setSelectedIds(new Set());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to bulk approve items';
      setError('Bulk approval failed: ' + message);
      setTimeout(() => setError(null), 5000);
    } finally {
      setBulkProcessing(false);
    }
  }, []);

  const handleBulkReject = useCallback(async (ids: string[], reason?: string) => {
    setBulkProcessing(true);
    setError(null);
    try {
      const client = getSupabaseRealtimeClient();
      for (const id of ids) {
        await rejectIngestion(client, id, reason);
      }
      setSelectedIds(new Set());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to bulk reject items';
      setError('Bulk rejection failed: ' + message);
      setTimeout(() => setError(null), 5000);
    } finally {
      setBulkProcessing(false);
    }
  }, []);

  // Escape CSV cells to prevent formula injection
  // Cells starting with =, +, -, @ can trigger formulas in Excel/Sheets
  const escapeCSVCell = (cell: string): string => {
    const cellStr = String(cell);
    // Check if cell starts with formula-inducing characters
    if (/^[=+\-@]/.test(cellStr)) {
      // Prepend with single quote to prevent formula execution
      const singleQuote = String.fromCharCode(39);
      const doubleQuote = String.fromCharCode(34);
      return singleQuote + singleQuote + cellStr.split(doubleQuote).join(doubleQuote + doubleQuote) + doubleQuote;
    }
    const doubleQuote = String.fromCharCode(34);
    return doubleQuote + cellStr.split(doubleQuote).join(doubleQuote + doubleQuote) + doubleQuote;
  };

  const handleExport = useCallback((ids: string[]) => {
    // Defensive: ensure items is always an array
    const safeItems = Array.isArray(items) ? items : [];
    const selectedItems = safeItems.filter(item => ids.includes(item.id));
    const headers = ['ID', 'Title', 'Source Type', 'Source URL', 'Status', 'Created At'];
    const rows = selectedItems.map(item => [
      item.id,
      item.title || 'Untitled',
      item.source_type,
      item.source_url || '',
      item.status,
      item.created_at,
    ]);

    const csv = [headers.join(','), ...rows.map(row => row.map(cell => escapeCSVCell(cell)).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const dateStr = new Date().toISOString().slice(0, 10);
    a.download = 'ingestion-queue-' + dateStr + '.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [items]);

  // Approval rules handlers
  const handleCreateRule = useCallback((rule: Omit<ApprovalRule, 'id' | 'createdAt' | 'matchCount' | 'lastMatchedAt'>) => {
    const newRule: ApprovalRule = {
      ...rule,
      id: 'rule-' + String(Date.now()),
      createdAt: new Date().toISOString(),
      matchCount: 0,
    };
    setRules(prev => [...prev, newRule]);
  }, []);

  const handleUpdateRule = useCallback((id: string, updates: Partial<ApprovalRule>) => {
    setRules(prev => prev.map(rule => rule.id === id ? { ...rule, ...updates } : rule));
  }, []);

  const handleDeleteRule = useCallback((id: string) => {
    setRules(prev => prev.filter(rule => rule.id !== id));
  }, []);

  const statusColor = {
    connecting: 'bg-yellow-400',
    connected: 'bg-green-500',
    disconnected: 'bg-gray-400',
    error: 'bg-red-500',
  }[status];

  return (
    <>
      {/* Skip link target - WCAG 2.1 SC 2.4.1 Bypass Blocks */}
      <main id="main-content" tabIndex={-1} className="p-6 space-y-6">
        <DashboardNavigation active="ingest" />

      {/* Error Display */}
      {error && <AlertBanner message={error} variant="error" onDismiss={() => setError(null)} />}

      <header className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">Ingestion Queue</h1>
            <div className="flex items-center gap-1.5 text-xs">
              <span className={cn('w-2 h-2 rounded-full', statusColor, 'animate-pulse')} />
              <span className="text-neutral-500">
                {status === 'connected' ? 'Live' : status}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRules(!showRules)}
              className={cn(
                'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                showRules ? 'bg-purple-600 text-white hover:bg-purple-700' : 'border border-purple-600 text-purple-600 hover:bg-purple-50'
              )}
              type="button"
            >
              {showRules ? 'Hide Rules' : 'Approval Rules'}
              {rules.length > 0 && ' (' + rules.filter(r => r.enabled).length + ')'}
            </button>
            {filter === 'pending' && items.length > 0 && (
              <button
                onClick={handleApproveAll}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
                type="button"
              >
                Approve All ({items.length})
              </button>
            )}
          </div>
        </div>
        <p className="text-sm text-neutral-600">
          Review and approve content for ingestion. YouTube videos, PDFs, and URLs await your decision.
        </p>
      </header>

      {/* Approval Rules Panel */}
      {showRules && (
        <ApprovalRulesConfig
          rules={rules}
          onCreateRule={handleCreateRule}
          onUpdateRule={handleUpdateRule}
          onDeleteRule={handleDeleteRule}
          processing={bulkProcessing}
        />
      )}

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Pending', value: stats.pending, color: 'bg-yellow-500' },
          { label: 'Approved', value: stats.approved, color: 'bg-blue-500' },
          { label: 'Processing', value: stats.processing, color: 'bg-purple-500' },
          { label: 'Completed', value: stats.completed, color: 'bg-green-500' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm"
          >
            <div className="flex items-center gap-2">
              <span className={cn('w-3 h-3 rounded-full', stat.color)} />
              <span className="text-sm text-neutral-500">{stat.label}</span>
            </div>
            <div className="mt-1 text-2xl font-semibold">{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div>
          <label className="block text-xs text-neutral-500 mb-1">Status</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as IngestionStatus | 'all')}
            className="rounded-lg border border-neutral-200 px-3 py-2 text-sm bg-white"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-neutral-500 mb-1">Source</label>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as IngestionSourceType | 'all')}
            className="rounded-lg border border-neutral-200 px-3 py-2 text-sm bg-white"
          >
            <option value="all">All Sources</option>
            <option value="youtube">YouTube</option>
            <option value="pdf">PDF</option>
            <option value="url">URL</option>
            <option value="upload">Upload</option>
            <option value="notebook">Notebook</option>
            <option value="rss">RSS</option>
          </select>
        </div>
      </div>

      {/* Bulk Actions Bar */}
      <BulkApprovalActions
        items={items}
        selectedIds={selectedIds}
        onSelectionChange={setSelectedIds}
        onApprove={handleBulkApprove}
        onReject={handleBulkReject}
        onExport={handleExport}
        processing={bulkProcessing}
        statusFilter={filter}
        sourceFilter={sourceFilter}
      />

      {/* Queue Items */}
      <div className="space-y-4">
        {items.length === 0 ? (
          <div className="rounded-lg border border-neutral-200 bg-white p-8 text-center">
            <div className="text-4xl mb-4">📭</div>
            <div className="text-neutral-500">
              No items in queue{filter !== 'all' ? ' with status "' + filter + '"' : ''}.
            </div>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className={cn(
                'rounded-lg bg-white shadow-sm overflow-hidden transition',
                selectedIds.has(item.id) ? 'border-2 border-blue-500' : 'border border-neutral-200'
              )}
            >
              <div className="flex">
                {/* Thumbnail */}
                <div className="w-48 h-32 bg-neutral-100 flex-shrink-0 relative">
                  {item.thumbnail_url ? (
                    <Image
                      src={item.thumbnail_url}
                      alt={item.title || 'Thumbnail'}
                      fill
                      className="object-cover"
                      sizes="192px"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-4xl">
                      {SOURCE_TYPE_ICONS[item.source_type]}
                    </div>
                  )}
                  {item.duration_seconds && (
                    <div className="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-1.5 py-0.5 rounded">
                      {formatDuration(item.duration_seconds)}
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 p-4">
                  <div className="flex items-start justify-between gap-4">
                    {/* Selection Checkbox */}
                    <BulkSelectionCheckbox
                      checked={selectedIds.has(item.id)}
                      selectable={item.status === 'pending'}
                      onToggle={() => {
                        const newSelection = new Set(selectedIds);
                        if (newSelection.has(item.id)) {
                          newSelection.delete(item.id);
                        } else {
                          newSelection.add(item.id);
                        }
                        setSelectedIds(newSelection);
                      }}
                    />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn('text-xs px-2 py-0.5 rounded-full', STATUS_COLORS[item.status])}>
                          {item.status}
                        </span>
                        <span className="text-xs text-neutral-400">
                          {SOURCE_TYPE_ICONS[item.source_type]} {item.source_type}
                        </span>
                        {item.priority > 0 && (
                          <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">
                            Priority: {item.priority}
                          </span>
                        )}
                      </div>
                      <h3 className="font-medium text-neutral-900 truncate">
                        {item.title || 'Untitled'}
                      </h3>
                      {item.description && (
                        <p className="text-sm text-neutral-500 line-clamp-2 mt-1">
                          {item.description}
                        </p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-neutral-400">
                        {item.source_meta?.channel_name ? (
                          <span>Channel: {String(item.source_meta.channel_name)}</span>
                        ) : null}
                        {item.source_meta?.uploader ? (
                          <span>By: {String(item.source_meta.uploader)}</span>
                        ) : null}
                        <span>{formatTimeAgo(item.created_at)}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    {item.status === 'pending' && (
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => handleReject(item.id)}
                          disabled={processing.has(item.id)}
                          className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
                        >
                          Reject
                        </button>
                        <button
                          onClick={() => handleApprove(item.id)}
                          disabled={processing.has(item.id)}
                          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                        >
                          {processing.has(item.id) ? 'Processing...' : 'Approve'}
                        </button>
                      </div>
                    )}

                    {item.status === 'failed' && item.error_message && (
                      <div className="text-xs text-red-600 max-w-xs">
                        Error: {item.error_message}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Source URL */}
              {item.source_url && (
                <div className="border-t border-neutral-100 px-4 py-2 bg-neutral-50">
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline truncate block"
                  >
                    {item.source_url}
                  </a>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      </main>
    </>
  );
}
