import { test } from "node:test";
import assert from "node:assert/strict";
import { agentThemeURL, fetchAgentTheme } from "../persona-resolver.js";

test("agentThemeURL is id-only by default (NO whoami, NO supabase)", () => {
  const u = agentThemeURL("4090-claude");
  assert.equal(u, "http://localhost:8054/v1/agent/theme/4090-claude");
  assert.ok(!u.includes("whoami"));
  assert.ok(!u.includes("supabase"));
});

test("agentThemeURL builds the alter path", () => {
  assert.equal(
    agentThemeURL("minimax", { alter: "minimax-ghost", gw: "http://h:8054/" }),
    "http://h:8054/v1/agent/theme/minimax/alter/minimax-ghost"
  );
});

test("fetchAgentTheme returns json via injected fetch", async () => {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    return { ok: true, status: 200, json: async () => ({ agent_id: "darkxside", color: "#E11D48", accent: "#F43F5E" }) };
  };
  const theme = await fetchAgentTheme("darkxside", { fetchImpl });
  assert.equal(theme.color, "#E11D48");
  assert.equal(calls[0], "http://localhost:8054/v1/agent/theme/darkxside");
});

test("fetchAgentTheme throws on non-ok", async () => {
  const fetchImpl = async () => ({ ok: false, status: 404, json: async () => ({}) });
  await assert.rejects(() => fetchAgentTheme("nope", { fetchImpl }), /404/);
});
