import { test } from "node:test";
import assert from "node:assert/strict";
import { applyPersonaThemeToRoot, clearPersona, setPersona } from "../theme-provider.js";

function fakeRoot() {
  const props = {};
  return {
    props,
    style: {
      setProperty: (k, v) => { props[k] = v; },
      removeProperty: (k) => { delete props[k]; },
    },
  };
}

test("applyPersonaThemeToRoot sets accent family, not signature", () => {
  const root = fakeRoot();
  applyPersonaThemeToRoot({ color: "#00FFCC", accent: "#5EEAD4" }, root);
  assert.equal(root.props["--pm-accent"], "#00FFCC");
  assert.equal(root.props["--pm-accent-soft"], "#5EEAD4");
  assert.equal(root.props["--pm-accent-2"], "#5EEAD4");
  assert.equal(root.props["--pm-signature"], undefined);
});

test("clearPersona removes only the accent family", () => {
  const root = fakeRoot();
  applyPersonaThemeToRoot({ color: "#00FFCC", accent: "#5EEAD4" }, root);
  clearPersona(root);
  assert.equal(root.props["--pm-accent"], undefined);
  assert.equal(root.props["--pm-accent-2"], undefined);
});

test("setPersona fetches then applies (injected fetch + root)", async () => {
  const root = fakeRoot();
  const fetchImpl = async () => ({ ok: true, status: 200, json: async () => ({ color: "#7C3AED", accent: "#A78BFA" }) });
  await setPersona("claude-opus", { root, fetchImpl });
  assert.equal(root.props["--pm-accent"], "#7C3AED");
});
