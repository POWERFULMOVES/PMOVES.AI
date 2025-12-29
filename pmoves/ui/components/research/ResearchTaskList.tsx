/* ═══════════════════════════════════════════════════════════════════════════
   Research Task List Component
   Displays list of research tasks with filtering and status tracking
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import type { ResearchTask, ResearchStatus } from "@/lib/api/research";

// Tailwind JIT static class lookup objects
const STATUS_BADGE_CLASSES: Record<ResearchStatus, string> = {
  pending: "bg-gray-100 text-gray-800",
  running: "bg-blue-100 text-blue-800 animate-pulse",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-yellow-100 text-yellow-800",
};

const STATUS_ICONS: Record<ResearchStatus, string> = {
  pending: "⏳",
  running: "🔄",
  completed: "✅",
  failed: "❌",
  cancelled: "⏹️",
};

const FILTER_OPTIONS: Array<{ value: ResearchStatus | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

interface ResearchTaskListProps {
  /** Tasks to display */
  tasks: ResearchTask[];
  /** ID of currently selected task */
  selectedId?: string;
  /** Callback when a task is selected */
  onSelect: (task: ResearchTask) => void;
  /** Callback to cancel a running task */
  onCancel?: (taskId: string) => void;
  /** Callback to refresh tasks */
  onRefresh: () => void;
  /** Whether refresh is in progress */
  refreshing?: boolean;
  /** Current status filter */
  statusFilter?: ResearchStatus | "all";
  /** Callback when filter changes */
  onStatusFilter?: (filter: ResearchStatus | "all") => void;
}

export function ResearchTaskList({
  tasks,
  selectedId,
  onSelect,
  onCancel,
  onRefresh,
  refreshing = false,
  statusFilter = "all",
  onStatusFilter,
}: ResearchTaskListProps) {
  const filteredTasks =
    statusFilter === "all"
      ? tasks
      : tasks.filter((task) => task.status === statusFilter);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="rounded border border-neutral-200 bg-white p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-medium">Research Tasks</h2>
          <span className="text-xs text-neutral-500">
            {filteredTasks.length} of {tasks.length}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {onStatusFilter && (
            <select
              value={statusFilter}
              onChange={(e) => onStatusFilter(e.target.value as ResearchStatus | "all")}
              className="text-xs rounded border border-neutral-300 px-2 py-1"
            >
              {FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="rounded border border-neutral-300 px-3 py-1 text-sm hover:bg-neutral-50 disabled:opacity-50 transition"
            aria-label="Refresh tasks"
          >
            {refreshing ? (
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              "Refresh"
            )}
          </button>
        </div>
      </div>

      {/* Task List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {filteredTasks.map((task) => (
          <div
            key={task.id}
            onClick={() => onSelect(task)}
            className={`
              p-3 rounded cursor-pointer transition border-2
              ${
                selectedId === task.id
                  ? "bg-blue-50 border-blue-500"
                  : "bg-neutral-50 border-transparent hover:bg-neutral-100 hover:border-neutral-300"
              }
            `}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE_CLASSES[task.status]} flex items-center gap-1 whitespace-nowrap`}
                  >
                    <span>{STATUS_ICONS[task.status]}</span>
                    {task.status}
                  </span>
                  <span className="text-xs text-neutral-500">{task.mode}</span>
                </div>
                <p className="text-sm font-medium line-clamp-2">{task.query}</p>
                <div className="text-xs text-neutral-500 mt-1 flex items-center gap-2">
                  <span>{formatDate(task.createdAt)}</span>
                  {task.iterations && (
                    <span>• {task.iterations} iterations</span>
                  )}
                </div>
              </div>

              {task.status === "running" && onCancel && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onCancel(task.id);
                  }}
                  className="text-xs text-red-600 hover:text-red-800 px-2 py-1 rounded hover:bg-red-50 transition"
                  aria-label="Cancel task"
                >
                  Cancel
                </button>
              )}
            </div>

            {/* Error message */}
            {task.status === "failed" && task.errorMessage && (
              <div className="mt-2 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                {task.errorMessage}
              </div>
            )}
          </div>
        ))}

        {filteredTasks.length === 0 && (
          <div className="text-center py-8 text-sm text-neutral-500">
            {tasks.length === 0 ? (
              <>
                <div className="text-2xl mb-2">🔬</div>
                <p>No research tasks yet.</p>
                <p className="text-xs">Start one above!</p>
              </>
            ) : (
              <p>No tasks match this filter.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
