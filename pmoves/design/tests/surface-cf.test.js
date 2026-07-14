// Tests for the CF-site (--c-*) persona adapter (DL-3.3).
import test from "node:test";
import assert from "node:assert/strict";
import { cfThemeVars, applyCfPersonaTheme, clearCfPersona } from "../surface-cf.js";

function fakeRoot() {
  const props = new Map();
  return {
    props,
    style: {
      setProperty: (k, v) => props.set(k, v),
      removeProperty: (k) => props.delete(k),
    },
  };
}

test("cfThemeVars maps color -> --c-accent and accent -> --c-accent-2", () => {
  assert.deepEqual(cfThemeVars({ color: "#0D9488", accent: "#2DD4BF" }), {
    "--c-accent": "#0D9488",
    "--c-accent-2": "#2DD4BF",
  });
});

test("cfThemeVars never emits background/ink overrides (spec D3)", () => {
  const vars = cfThemeVars({ color: "#111111", accent: "#222222", bg: "#000", ink: "#fff" });
  const keys = Object.keys(vars);
  assert.deepEqual(keys.sort(), ["--c-accent", "--c-accent-2"]);
  for (const k of keys) assert.match(k, /^--c-accent/);
});

test("cfThemeVars tolerates missing/partial/junk themes", () => {
  assert.deepEqual(cfThemeVars(null), {});
  assert.deepEqual(cfThemeVars("nope"), {});
  assert.deepEqual(cfThemeVars({ accent: "#FB7185" }), { "--c-accent-2": "#FB7185" });
});

test("applyCfPersonaTheme sets exactly the mapped props; clearCfPersona reverts", () => {
  const root = fakeRoot();
  const vars = applyCfPersonaTheme({ color: "#E11D48", accent: "#FB7185" }, root);
  assert.equal(root.props.get("--c-accent"), "#E11D48");
  assert.equal(root.props.get("--c-accent-2"), "#FB7185");
  assert.equal(root.props.size, Object.keys(vars).length);

  clearCfPersona(root);
  assert.equal(root.props.size, 0);
});
