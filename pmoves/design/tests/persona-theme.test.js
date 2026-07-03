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
