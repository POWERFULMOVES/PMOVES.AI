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
