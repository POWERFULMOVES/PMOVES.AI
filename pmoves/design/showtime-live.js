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
 * feed (CORS/4xx) instead of silently freezing on the last stage. Returns { close() }.
 */
export function watchShowtime(opts = {}) {
  const gw = String(opts.gw || DEFAULT_GW).replace(/\/+$/, "");
  const onState = opts.onState || (() => {});
  const onError = opts.onError || (() => {});
  const ES = opts.EventSourceImpl || (typeof EventSource !== "undefined" ? EventSource : null);
  if (!ES) return { close() {} };
  const es = new ES(gw + "/sse/events");
  const handleFrame = (m) => {
    let data;
    try { data = JSON.parse(m.data); } catch { return; }
    onState(stageFromShowtimeEvent(data));
  };
  // Unnamed frames (tests / any default `message`) + the backend's NAMED subjects.
  es.onmessage = handleFrame;
  if (typeof es.addEventListener === "function") {
    for (const evt of LIVE_EVENTS) es.addEventListener(evt, handleFrame);
  }
  es.onerror = (e) => onError(e, es.readyState);
  return { close: () => es.close() };
}
