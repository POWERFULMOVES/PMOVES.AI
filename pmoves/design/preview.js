// pmoves/design/preview.js
import { toggleTheme } from "./theme-provider.js";
import { setPersona, clearPersona } from "./theme-provider.js";
import { applyStage } from "./showtime-live.js";
import { resolvePersonaFromURL, alterOptions } from "./persona-theme.js";

const $ = (id) => document.getElementById(id);
let SIGNATURES = {};
const url = resolvePersonaFromURL(location.search);
const GW = (url && url.gw) || "http://localhost:8054";
const status = (msg) => { $("persona-status").textContent = msg; };

$("toggle").addEventListener("click", () => toggleTheme());

// Populate persona dropdown from the gateway signature registry.
async function loadPersonas() {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 5000); // fail fast if the gateway hangs
  try {
    const res = await fetch(`${GW}/v1/agent/signatures`, { signal: ctl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { signatures } = await res.json();
    SIGNATURES = signatures;
    const sel = $("persona");
    for (const id of Object.keys(signatures)) {
      const o = document.createElement("option");
      o.value = id; o.textContent = signatures[id].display_name || id;
      sel.appendChild(o);
    }
  } catch (e) {
    status(`gateway offline (${GW}) — base theme only`);
  } finally {
    clearTimeout(timer);
  }
}

function populateAlters(id) {
  const sel = $("alter");
  sel.length = 1; // keep the "— none —" option (index 0)
  for (const { value, label } of alterOptions(SIGNATURES[id])) {
    const o = document.createElement("option");
    o.value = value; o.textContent = label;
    sel.appendChild(o);
  }
}

// Apply a persona. An explicit override (from ?agent=) wins over the dropdown,
// so a URL persona still resolves even if its option never loaded (gateway/CORS
// offline) — otherwise a stale/empty dropdown would silently clear the persona.
async function apply(override = {}) {
  const id = override.id ?? $("persona").value;
  const alter = override.alter ?? ($("alter").value || null);
  if (!id) { clearPersona(); status("base theme"); return; }
  try {
    await setPersona(id, { alter, gw: GW });
    status(`persona: ${id}${alter ? " / " + alter : ""}`);
  } catch (e) {
    status(`failed: ${e.message}`);
  }
}

$("persona").addEventListener("change", () => { populateAlters($("persona").value); apply(); });
$("alter").addEventListener("change", () => apply());
$("live").addEventListener("change", (e) => applyStage(e.target.checked ? "live" : null));

await loadPersonas();
// honor ?agent= on load — apply the URL id directly (dropdown is just UI state)
if (url && url.id) {
  $("persona").value = url.id;
  populateAlters(url.id);
  if (url.alter) $("alter").value = url.alter;
  await apply({ id: url.id, alter: url.alter || null });
}
