import { test } from "node:test";
import assert from "node:assert/strict";
import { applyStage, watchShowtime } from "../showtime-live.js";

function fakeRoot() {
  const dataset = {};
  return { dataset };
}

test("applyStage sets/clears data-stage", () => {
  const root = fakeRoot();
  applyStage("live", root);
  assert.equal(root.dataset.stage, "live");
  applyStage(null, root);
  assert.equal(root.dataset.stage, undefined);
});

// Fake EventSource that supports BOTH the default onmessage/onerror handlers
// and addEventListener for NAMED frames — the real Showtime backend frames every
// event with `event: {subject}` (e.g. showtime.all_green.v1), which onmessage
// never receives.
class NamedES {
  constructor(url) {
    this.url = url;
    this.listeners = {};
    NamedES.last = this;
  }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  emitNamed(type, data) { if (this.listeners[type]) this.listeners[type]({ data }); }
  fail() { if (this.onerror) this.onerror(new Error("sse down")); }
  close() { this.closed = true; }
}

test("watchShowtime maps an SSE 'showtime' message to onState('live')", () => {
  const seen = [];
  let inst;
  class StubES {
    constructor(url) { this.url = url; inst = this; }
    close() { this.closed = true; }
  }
  const handle = watchShowtime({
    gw: "http://localhost:9225",
    EventSourceImpl: StubES,
    onState: (s) => seen.push(s),
  });
  assert.equal(inst.url, "http://localhost:9225/sse/events");
  inst.onmessage({ data: JSON.stringify({ state: "showtime", source: "showtime-api" }) });
  inst.onmessage({ data: JSON.stringify({ state: "hold" }) });
  inst.onmessage({ data: "not json" });
  assert.deepEqual(seen, ["live", null]);
  handle.close();
  assert.equal(inst.closed, true);
});

test("watchShowtime flips on the NAMED showtime.all_green.v1 frame (real backend format)", () => {
  const seen = [];
  watchShowtime({
    EventSourceImpl: NamedES,
    onState: (s) => seen.push(s),
  });
  // Real Showtime emits `event: showtime.all_green.v1` — onmessage never fires for this.
  NamedES.last.emitNamed(
    "showtime.all_green.v1",
    JSON.stringify({ state: "showtime", source: "showtime-api" }),
  );
  assert.deepEqual(seen, ["live"]);
});

test("watchShowtime surfaces SSE failures via onError", () => {
  const errs = [];
  watchShowtime({
    EventSourceImpl: NamedES,
    onError: (e) => errs.push(e),
  });
  NamedES.last.fail();
  assert.equal(errs.length, 1);
});

// --- Spec D4 poll fallback: GET {gw}/health/all -> {state} -> onState(stage). ---

test("watchShowtime polls /health/all after an SSE error", async () => {
  const seen = [];
  let inst;
  class StubES {
    constructor(url) { this.url = url; inst = this; }
    close() { this.closed = true; }
  }
  let tickFn = null;
  const setIntervalImpl = (fn) => { tickFn = fn; return 42; };
  let fetchedUrl = null;
  const fetchImpl = async (url) => {
    fetchedUrl = url;
    return { ok: true, json: async () => ({ state: "showtime" }) };
  };
  watchShowtime({
    gw: "http://localhost:9225",
    EventSourceImpl: StubES,
    fetchImpl,
    setIntervalImpl,
    onState: (s) => seen.push(s),
  });
  assert.equal(tickFn, null); // no poll before the SSE fails
  inst.onerror(new Error("sse down"));
  assert.equal(typeof tickFn, "function"); // poll started on error
  await tickFn();
  assert.deepEqual(seen, ["live"]);
  assert.equal(fetchedUrl, "http://localhost:9225/health/all");
});

test("watchShowtime polls when EventSource is unavailable", async () => {
  const seen = [];
  let tickFn = null;
  const setIntervalImpl = (fn) => { tickFn = fn; return 1; };
  const fetchImpl = async () => ({ ok: true, json: async () => ({ state: "showtime" }) });
  watchShowtime({
    EventSourceImpl: null,
    fetchImpl,
    setIntervalImpl,
    onState: (s) => seen.push(s),
  });
  assert.equal(typeof tickFn, "function"); // polls straight away with no SSE
  await tickFn();
  assert.deepEqual(seen, ["live"]);
});

test("watchShowtime close() clears the poll timer", () => {
  const cleared = [];
  const setIntervalImpl = () => 99;
  const clearIntervalImpl = (h) => cleared.push(h);
  const fetchImpl = async () => ({ ok: true, json: async () => ({ state: "hold" }) });
  const handle = watchShowtime({
    EventSourceImpl: null,
    fetchImpl,
    setIntervalImpl,
    clearIntervalImpl,
    onState: () => {},
  });
  handle.close();
  assert.deepEqual(cleared, [99]);
});

test("watchShowtime poll:false disables the fallback", () => {
  let called = false;
  const setIntervalImpl = () => { called = true; return 1; };
  let inst;
  class StubES {
    constructor(url) { this.url = url; inst = this; }
    close() {}
  }
  watchShowtime({
    EventSourceImpl: StubES,
    fetchImpl: async () => ({ ok: true, json: async () => ({}) }),
    setIntervalImpl,
    poll: false,
    onState: () => {},
  });
  inst.onerror(new Error("down"));
  assert.equal(called, false); // SSE-only: no polling even on error
});
