// pmoves/design/showtime-live.js — browser bridge to Showtime (:9225) for the "live" flip.
// SSE over GET /sse/events; no NATS-in-browser needed (spec D4).
import { stageFromShowtimeEvent } from "./persona-theme.js";

const DEFAULT_GW = "http://localhost:9225";

// The Showtime backend frames every SSE as a NAMED event (`event: {subject}`);
// EventSource.onmessage only receives UNNAMED (default `message`) frames, so we
// must also addEventListener for the live-flip subject. See showtime-api/nats_sse.py.
const LIVE_EVENTS = ["showtime.all_green.v1"];

/** Set or clear documentElement[data-stage]. */
export function applyStage(stage, root = document.documentElement) {
  if (stage) root.dataset.stage = stage;
  else delete root.dataset.stage;
}

/**
 * Subscribe to Showtime SSE and call onState(stage) on each event.
 * EventSourceImpl is injectable for tests. opts.onError(err) surfaces a broken
 * feed (CORS/4xx) instead of silently freezing on the last stage.
 *
 * Spec D4 poll fallback: when SSE errors (or EventSource is unavailable), poll
 * GET {gw}/health/all -> {state} and map it through stageFromShowtimeEvent so the
 * live flip still works over a broken feed. Injectables (fetchImpl/setIntervalImpl/
 * clearIntervalImpl) keep tests hermetic; opts.pollMs overrides the 5s interval;
 * opts.poll === false disables polling (SSE-only). Returns { close() }.
 */
export function watchShowtime(opts = {}) {
  const gw = String(opts.gw || DEFAULT_GW).replace(/\/+$/, "");
  const onState = opts.onState || (() => {});
  const onError = opts.onError || (() => {});
  const ES = opts.EventSourceImpl || (typeof EventSource !== "undefined" ? EventSource : null);

  // --- Poll fallback wiring (spec D4). ---
  const pollEnabled = opts.poll !== false;
  const fetchImpl = opts.fetchImpl || (typeof fetch !== "undefined" ? fetch.bind(globalThis) : null);
  const setIntervalImpl = opts.setIntervalImpl || (typeof setInterval !== "undefined" ? setInterval : null);
  const clearIntervalImpl = opts.clearIntervalImpl || (typeof clearInterval !== "undefined" ? clearInterval : null);
  const pollMs = opts.pollMs || 5000;
  const canPoll = pollEnabled && !!fetchImpl && !!setIntervalImpl;
  let pollTimer = null;
  let ticking = false; // guard against overlapping ticks
  let sseDown = false;

  function startPolling() {
    if (!canPoll || pollTimer !== null) return;
    pollTimer = setIntervalImpl(pollTick, pollMs);
  }
  function stopPolling() {
    if (pollTimer !== null && clearIntervalImpl) {
      clearIntervalImpl(pollTimer);
      pollTimer = null;
    }
  }
  // Poll while LIVE or while the SSE feed is DOWN. The backend only publishes
  // `showtime.all_green.v1` when ENTERING showtime — it never sends a hold/
  // preflight frame — so SSE can turn the badge on but never off. The /health/all
  // poll returns the real current state, so it is the only way to clear once
  // live. When SSE is healthy the poll is idle unless we are live (waiting for
  // the exit SSE won't announce), which bounds the probe cost to live sessions.
  function reconcilePoll(stage) {
    if (stage === "live" || sseDown) startPolling();
    else stopPolling();
  }
  function emit(stage) {
    onState(stage);
    reconcilePoll(stage);
  }

  async function pollTick() {
    if (ticking) return;
    ticking = true;
    try {
      const res = await fetchImpl(gw + "/health/all");
      if (res && res.ok) {
        const json = await res.json();
        emit(stageFromShowtimeEvent(json));
      }
    } catch {
      // Best-effort: never throw out of the timer.
    } finally {
      ticking = false;
    }
  }

  // No EventSource in this environment: the poll is the sole state source.
  if (!ES) {
    sseDown = true;
    startPolling();
    return { close: () => stopPolling() };
  }

  const es = new ES(gw + "/sse/events");
  const handleFrame = (m) => {
    sseDown = false; // a frame means the feed is healthy again
    let data;
    try { data = JSON.parse(m.data); } catch { return; }
    emit(stageFromShowtimeEvent(data));
  };
  // Unnamed frames (tests / any default `message`) + the backend's NAMED subjects.
  es.onmessage = handleFrame;
  if (typeof es.addEventListener === "function") {
    for (const evt of LIVE_EVENTS) es.addEventListener(evt, handleFrame);
  }
  es.onerror = (e) => {
    onError(e, es.readyState);
    sseDown = true;
    startPolling(); // fall back to /health/all when the feed breaks
  };
  return {
    close: () => {
      stopPolling();
      es.close();
    },
  };
}
