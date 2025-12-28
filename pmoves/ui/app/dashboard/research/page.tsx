"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
import { TaskInitiationForm, type ResearchOptions } from "../../../components/research/TaskInitiationForm";
import { ResearchTaskList } from "../../../components/research/ResearchTaskList";
import { ResearchResults } from "../../../components/research/ResearchResults";
import {
  initiateResearch,
  listResearchTasks,
  getResearchResults,
  cancelResearch,
  researchHealth,
  publishToNotebook,
} from "../../../lib/api/research";
import type { ResearchTask, ResearchResult } from "../../../lib/api/research";

export default function ResearchDashboardPage() {
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<ResearchTask | null>(null);
  const [results, setResults] = useState<ResearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [healthy, setHealthy] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | ResearchTask["status"]>("all");

  // Ref to track current tasks for polling check (prevents stale closure issues)
  const tasksRef = useRef<ResearchTask[]>([]);
  tasksRef.current = tasks;

  const refreshTasks = useCallback(async () => {
    setRefreshing(true);
    const result = await listResearchTasks({ limit: 50 });
    if (result.ok) {
      setTasks(result.data);
    } else {
      setError(result.error);
      setTimeout(() => setError(null), 5000);
    }
    setRefreshing(false);
  }, []);

  const checkHealth = useCallback(async () => {
    const result = await researchHealth();
    if (result.ok) {
      setHealthy(result.data.healthy);
    }
  }, []);

  useEffect(() => {
    refreshTasks();
    checkHealth();
    // Poll for updates on running tasks - uses ref to avoid dependency on tasks state
    const interval = setInterval(() => {
      const hasRunning = tasksRef.current.some(t => t.status === "running");
      if (hasRunning) {
        refreshTasks();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [refreshTasks, checkHealth]);

  const handleInitiate = async (query: string, options: ResearchOptions) => {
    setStarting(true);
    setError(null);

    const result = await initiateResearch(query, options);
    if (result.ok) {
      await refreshTasks();
    } else {
      setError(result.error);
    }

    setStarting(false);
  };

  const handleSelectTask = async (task: ResearchTask) => {
    setSelectedTask(task);
    setResults(null);

    if (task.status === "completed") {
      const result = await getResearchResults(task.id);
      if (result.ok) {
        setResults(result.data);
      }
    }
  };

  const handleCancel = async (taskId: string) => {
    const result = await cancelResearch(taskId);
    if (result.ok) {
      await refreshTasks();
    }
  };

  const handlePublish = async () => {
    if (!selectedTask) return;
    setPublishing(true);

    const result = await publishToNotebook(selectedTask.id, "default");
    if (result.ok) {
      setSuccessMessage("Results published to notebook");
      setTimeout(() => setSuccessMessage(null), 3000);
    } else {
      setError(result.error);
    }

    setPublishing(false);
  };

  return (
    <>
      {/* Skip link target - WCAG 2.1 SC 2.4.1 Bypass Blocks */}
      <main id="main-content" tabIndex={-1} className="p-6 space-y-6">
        <DashboardNavigation active="research" />

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Deep Research</h1>
        <p className="text-sm text-neutral-600">
          Initiate and manage deep research tasks using PMOVES AI research orchestration.
        </p>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`px-2 py-1 rounded ${
              healthy
                ? "bg-green-100 text-green-800"
                : "bg-red-100 text-red-800"
            }`}
          >
            DeepResearch: {healthy ? "Connected" : "Disconnected"}
          </span>
          {tasks.filter(t => t.status === "running").length > 0 && (
            <span className="px-2 py-1 rounded bg-blue-100 text-blue-800 flex items-center gap-1">
              <span className="animate-pulse">●</span>
              {tasks.filter(t => t.status === "running").length} running
            </span>
          )}
        </div>
      </header>

      {/* Error Display */}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800" role="alert" aria-live="assertive">
          <div className="flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800"
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Success Message Display */}
      {successMessage && (
        <div className="rounded border border-green-300 bg-green-50 p-4 text-sm text-green-800" role="status" aria-live="polite">
          <div className="flex items-center justify-between">
            <span>{successMessage}</span>
            <button
              onClick={() => setSuccessMessage(null)}
              className="text-green-600 hover:text-green-800"
              aria-label="Dismiss success message"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Task Initiation Form */}
      <TaskInitiationForm
        onSubmit={handleInitiate}
        loading={starting}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Task List */}
        <section className="lg:col-span-1">
          <ResearchTaskList
            tasks={tasks}
            selectedId={selectedTask?.id}
            onSelect={handleSelectTask}
            onCancel={handleCancel}
            onRefresh={refreshTasks}
            refreshing={refreshing}
            statusFilter={statusFilter}
            onStatusFilter={setStatusFilter}
          />
        </section>

        {/* Task Details */}
        <section className="lg:col-span-2 rounded border border-neutral-200 bg-white p-4">
          {selectedTask ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h2 className="text-lg font-medium">Task Details</h2>
                  <p className="text-sm text-neutral-600 mt-1 line-clamp-2">
                    {selectedTask.query}
                  </p>
                </div>
                <span
                  className={`text-sm px-3 py-1 rounded ${
                    selectedTask.status === "pending"
                      ? "bg-gray-100 text-gray-800"
                      : selectedTask.status === "running"
                      ? "bg-blue-100 text-blue-800"
                      : selectedTask.status === "completed"
                      ? "bg-green-100 text-green-800"
                      : selectedTask.status === "failed"
                      ? "bg-red-100 text-red-800"
                      : "bg-yellow-100 text-yellow-800"
                  }`}
                >
                  {selectedTask.status}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-neutral-500">Mode:</span>{" "}
                  <span className="font-medium">{selectedTask.mode}</span>
                </div>
                <div>
                  <span className="text-neutral-500">Created:</span>{" "}
                  <span className="font-medium">
                    {new Date(selectedTask.createdAt).toLocaleString()}
                  </span>
                </div>
                {selectedTask.startedAt && (
                  <div>
                    <span className="text-neutral-500">Started:</span>{" "}
                    <span className="font-medium">
                      {new Date(selectedTask.startedAt).toLocaleString()}
                    </span>
                  </div>
                )}
                {selectedTask.iterations && (
                  <div>
                    <span className="text-neutral-500">Iterations:</span>{" "}
                    <span className="font-medium">{selectedTask.iterations}</span>
                  </div>
                )}
              </div>

              {/* Running task progress */}
              {selectedTask.status === "running" && (
                <div className="flex items-center gap-2 text-sm text-blue-600">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Research in progress...
                  {selectedTask.iterations && ` (${selectedTask.iterations} iterations)`}
                </div>
              )}

              {selectedTask.status === "running" && (
                <button
                  onClick={() => handleCancel(selectedTask.id)}
                  className="rounded border border-red-600 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  Cancel Research
                </button>
              )}

              {results && (
                <div className="border-t pt-4">
                  <h3 className="font-medium mb-4">Research Results</h3>
                  <ResearchResults
                    result={results}
                    onPublish={handlePublish}
                    publishing={publishing}
                  />
                </div>
              )}

              {selectedTask.status === "completed" && !results && (
                <div className="text-center py-8 text-neutral-500">
                  <button
                    onClick={() => handleSelectTask(selectedTask)}
                    className="text-blue-600 hover:underline"
                  >
                    Load Results
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-neutral-500">
              <div className="text-4xl mb-4">🔬</div>
              <p>Select a task to view details</p>
            </div>
          )}
        </section>
      </div>
      </main>
    </>
  );
}
