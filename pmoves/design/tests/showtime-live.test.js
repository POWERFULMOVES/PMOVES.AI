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
