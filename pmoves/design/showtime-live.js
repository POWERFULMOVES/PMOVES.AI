// pmoves/design/showtime-live.js — browser bridge to Showtime (:9225) for the "live" flip.
// SSE over GET /sse/events; no NATS-in-browser needed (spec D4).
import { stageFromShowtimeEvent } from "./persona-theme.js";

const DEFAULT_GW = "http://localhost:9225";

/** Set or clear documentElement[data-stage]. */
export function applyStage(stage, root = document.documentElement) {
  if (stage) root.dataset.stage = stage;
  else delete root.dataset.stage;
}

/**
 * Subscribe to Showtime SSE and call onState(stage) on each event.
 * EventSourceImpl is injectable for tests. Returns { close() }.
 */
export function watchShowtime(opts = {}) {
  const gw = String(opts.gw || DEFAULT_GW).replace(/\/+$/, "");
  const onState = opts.onState || (() => {});
  const ES = opts.EventSourceImpl || (typeof EventSource !== "undefined" ? EventSource : null);
  if (!ES) return { close() {} };
  const es = new ES(gw + "/sse/events");
  es.onmessage = (m) => {
    let data;
    try { data = JSON.parse(m.data); } catch { return; }
    onState(stageFromShowtimeEvent(data));
  };
  return { close: () => es.close() };
}
