"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
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
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export default function IngestionQueuePage() {
  const [items, setItems] = useState<IngestionQueueItem[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [filter, setFilter] = useState<IngestionStatus | 'all'>('pending');
  const [sourceFilter, setSourceFilter] = useState<IngestionSourceType | 'all'>('all');
  const [processing, setProcessing] = useState<Set<string>>(new Set());
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
          setItems(data);

          // Calculate stats
          const allItems = await fetchIngestionQueue(client, { limit: 1000 });
          const statsMap = allItems.reduce((acc, item) => {
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
            if (isMounted) {
              setItems((prev) => {
                if (prev.some((i) => i.id === item.id)) return prev;
                // Add to list if matches filter
                if (filter !== 'all' && item.status !== filter) return prev;
                if (sourceFilter !== 'all' && item.source_type !== sourceFilter) return prev;
                return [item, ...prev];
              });
              setStats((prev) => ({
                ...prev,
                [item.status]: (prev[item.status as keyof typeof prev] || 0) + 1,
              }));
            }
          },
          onUpdate: (item) => {
            if (isMounted) {
              setItems((prev) => {
                // If item no longer matches filter, remove it
                if (filter !== 'all' && item.status !== filter) {
                  return prev.filter((i) => i.id !== item.id);
                }
                return prev.map((i) => (i.id === item.id ? item : i));
              });
            }
          },
          onDelete: (item) => {
            if (isMounted) {
              setItems((prev) => prev.filter((i) => i.id !== item.id));
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
      console.error('Failed to approve:', error);
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
      console.error('Failed to reject:', error);
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

  const statusColor = {
    connecting: 'bg-yellow-400',
    connected: 'bg-green-500',
    disconnected: 'bg-gray-400',
    error: 'bg-red-500',
  }[status];

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="ingest" />

      <header className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">Ingestion Queue</h1>
            <div className="flex items-center gap-1.5 text-xs">
              <span className={`w-2 h-2 rounded-full ${statusColor} animate-pulse`} />
              <span className="text-neutral-500">
                {status === 'connected' ? 'Live' : status}
              </span>
            </div>
          </div>
          {filter === 'pending' && items.length > 0 && (
            <button
              onClick={handleApproveAll}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
            >
              Approve All ({items.length})
            </button>
          )}
        </div>
        <p className="text-sm text-neutral-600">
          Review and approve content for ingestion. YouTube videos, PDFs, and URLs await your decision.
        </p>
      </header>

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
              <span className={`w-3 h-3 rounded-full ${stat.color}`} />
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

      {/* Queue Items */}
      <div className="space-y-4">
        {items.length === 0 ? (
          <div className="rounded-lg border border-neutral-200 bg-white p-8 text-center">
            <div className="text-4xl mb-4">📭</div>
            <div className="text-neutral-500">
              No items in queue{filter !== 'all' ? ` with status "${filter}"` : ''}.
            </div>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="rounded-lg border border-neutral-200 bg-white shadow-sm overflow-hidden"
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
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[item.status]}`}>
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
    </div>
  );
}
