import { test } from "node:test";
import assert from "node:assert/strict";
import { personaThemeVars } from "../persona-theme.js";

test("runner smoke", () => {
  assert.equal(1 + 1, 2);
});

test("personaThemeVars maps color->accent, accent->soft+2", () => {
  const v = personaThemeVars({ color: "#00FFCC", accent: "#5EEAD4" });
  assert.equal(v["--pm-accent"], "#00FFCC");
  assert.equal(v["--pm-accent-soft"], "#5EEAD4");
  assert.equal(v["--pm-accent-2"], "#5EEAD4");
});

test("personaThemeVars NEVER sets signature/bg/ink (canon guard)", () => {
  const v = personaThemeVars({ color: "#00FFCC", accent: "#5EEAD4" });
  assert.equal(v["--pm-signature"], undefined);
  assert.equal(v["--pm-bg"], undefined);
  assert.equal(v["--pm-ink"], undefined);
  assert.equal(v["--pm-void"], undefined);
});

test("personaThemeVars tolerates missing fields", () => {
  assert.deepEqual(personaThemeVars({}), {});
  assert.deepEqual(personaThemeVars(null), {});
  assert.deepEqual(personaThemeVars({ color: "#abc" }), { "--pm-accent": "#abc" });
});

// Task 3 — resolvePersonaFromURL
import { resolvePersonaFromURL } from "../persona-theme.js";

test("resolvePersonaFromURL parses agent/alter/gw", () => {
  assert.deepEqual(
    resolvePersonaFromURL("?agent=darkxside&alter=ghost&gw=http://h:8054"),
    { id: "darkxside", alter: "ghost", gw: "http://h:8054" }
  );
});

test("resolvePersonaFromURL defaults alter/gw to null", () => {
  assert.deepEqual(resolvePersonaFromURL("?agent=4090-claude"), {
    id: "4090-claude", alter: null, gw: null,
  });
});

test("resolvePersonaFromURL returns null with no agent", () => {
  assert.equal(resolvePersonaFromURL(""), null);
  assert.equal(resolvePersonaFromURL("?foo=1"), null);
});

// Task 4 — stageFromShowtimeEvent
import { stageFromShowtimeEvent } from "../persona-theme.js";

test("stageFromShowtimeEvent: showtime -> live", () => {
  assert.equal(stageFromShowtimeEvent({ state: "showtime" }), "live");
  assert.equal(stageFromShowtimeEvent("showtime"), "live");
});

test("stageFromShowtimeEvent: hold/preflight/junk -> null", () => {
  assert.equal(stageFromShowtimeEvent({ state: "hold" }), null);
  assert.equal(stageFromShowtimeEvent({ state: "preflight" }), null);
  assert.equal(stageFromShowtimeEvent(null), null);
  assert.equal(stageFromShowtimeEvent({}), null);
});

import { alterOptions } from "../persona-theme.js";

test("alterOptions maps a signature's alters to {value,label}", () => {
  const sig = { alters: [
    { name: "minimax-ghost", display_name: "MiniMax Ghost" },
    { id: "z890-infra" },
  ]};
  assert.deepEqual(alterOptions(sig), [
    { value: "minimax-ghost", label: "MiniMax Ghost" },
    { value: "z890-infra", label: "z890-infra" },
  ]);
});

test("alterOptions is empty for no alters", () => {
  assert.deepEqual(alterOptions({}), []);
  assert.deepEqual(alterOptions(null), []);
  assert.deepEqual(alterOptions({ alters: [] }), []);
});
