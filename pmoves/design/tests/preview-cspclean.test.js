import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const html = readFileSync(fileURLToPath(new URL("../preview.html", import.meta.url)), "utf8");

test("preview.html has no inline <script> (CSP-clean)", () => {
  const scripts = html.match(/<script\b[^>]*>/gi) || [];
  for (const s of scripts) assert.ok(/\bsrc=/.test(s), `inline script: ${s}`);
});

test("preview.html has no inline <style> block", () => {
  assert.ok(!/<style\b/i.test(html), "inline <style> present");
});

test("preview.html exposes the persona + alter pickers + live toggle", () => {
  assert.ok(/id="persona"/.test(html), "missing #persona select");
  assert.ok(/id="alter"/.test(html), "missing #alter select");
  assert.ok(/id="live"/.test(html), "missing #live toggle");
});
