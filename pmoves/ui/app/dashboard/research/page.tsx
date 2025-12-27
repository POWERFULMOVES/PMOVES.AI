"use client";

import { useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
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
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    refreshTasks();
    checkHealth();
  }, []);

  const refreshTasks = async () => {
    const result = await listResearchTasks({ limit: 20 });
    if (result.ok) {
      setTasks(result.data);
    }
  };

  const checkHealth = async () => {
    const result = await researchHealth();
    if (result.ok) {
      setHealthy(result.data.healthy);
    }
  };

  const handleInitiate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    const result = await initiateResearch(query, {
      mode: "tensorzero",
      maxIterations: 10,
    });

    if (result.ok) {
      setQuery("");
      await refreshTasks();
    } else {
      setError(result.error);
    }

    setLoading(false);
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
    // For now, just show success - actual implementation needs notebook selection
    alert("Research results would be published to Open Notebook");
  };

  const statusColors: Record<ResearchTask["status"], string> = {
    pending: "bg-gray-100 text-gray-800",
    running: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    cancelled: "bg-yellow-100 text-yellow-800",
  };

  return (
    <div className="p-6 space-y-6">
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
        </div>
      </header>

      {/* New Research Form */}
      <section className="rounded border border-neutral-200 bg-white p-4">
        <h2 className="text-lg font-medium mb-4">Start New Research</h2>
        <form onSubmit={handleInitiate} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter research question..."
            className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "Starting..." : "Start Research"}
          </button>
        </form>
        {error && (
          <div className="mt-3 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Task List */}
        <section className="lg:col-span-1 rounded border border-neutral-200 bg-white p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Research Tasks</h2>
            <button
              onClick={refreshTasks}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              Refresh
            </button>
          </div>

          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                onClick={() => handleSelectTask(task)}
                className={`p-3 rounded cursor-pointer transition ${
                  selectedTask?.id === task.id
                    ? "bg-blue-50 border-2 border-blue-500"
                    : "bg-neutral-50 border-2 border-transparent hover:bg-neutral-100"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium line-clamp-2">
                    {task.query}
                  </p>
                  <span
                    className={`text-xs px-2 py-0.5 rounded whitespace-nowrap ${statusColors[task.status]}`}
                  >
                    {task.status}
                  </span>
                </div>
                <p className="text-xs text-neutral-500 mt-1">
                  {new Date(task.createdAt).toLocaleString()}
                </p>
              </div>
            ))}
          </div>

          {tasks.length === 0 && (
            <div className="text-center text-sm text-neutral-500 py-8">
              No research tasks yet. Start one above!
            </div>
          )}
        </section>

        {/* Task Details */}
        <section className="lg:col-span-2 rounded border border-neutral-200 bg-white p-4">
          {selectedTask ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-medium">Task Details</h2>
                  <p className="text-sm text-neutral-600 mt-1">
                    {selectedTask.query}
                  </p>
                </div>
                <span
                  className={`text-sm px-3 py-1 rounded ${statusColors[selectedTask.status]}`}
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

              {selectedTask.status === "running" && (
                <button
                  onClick={() => handleCancel(selectedTask.id)}
                  className="rounded border border-red-600 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  Cancel Research
                </button>
              )}

              {results && (
                <div className="space-y-4 border-t pt-4">
                  <h3 className="font-medium">Research Results</h3>
                  <div className="bg-neutral-50 rounded p-4">
                    <p className="text-sm">{results.summary}</p>
                  </div>
                  {results.notes.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Notes</h4>
                      <ul className="space-y-2">
                        {results.notes.map((note, i) => (
                          <li
                            key={i}
                            className="text-sm bg-neutral-50 rounded p-2"
                          >
                            {note}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {results.sources.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Sources</h4>
                      <ul className="space-y-1">
                        {results.sources.map((source, i) => (
                          <li
                            key={i}
                            className="text-sm text-blue-600 hover:underline"
                          >
                            <a href={source.url} target="_blank" rel="noreferrer">
                              {source.title}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <button
                    onClick={handlePublish}
                    className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                  >
                    Publish to Notebook
                  </button>
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
              Select a task to view details
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
