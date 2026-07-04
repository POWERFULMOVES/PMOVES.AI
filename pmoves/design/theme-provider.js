// pmoves/design/theme-provider.js — dependency-free theme switch + persona resolver.
// DL-1: setTheme/toggleTheme (data-theme). DL-3: setPersona() resolves the active
// agent's accent family via the BoTZ Gateway /v1/agent/theme/{id} (accent-override).
import { personaThemeVars } from "./persona-theme.js";
import { fetchAgentTheme } from "./persona-resolver.js";

export function setTheme(name) { document.documentElement.setAttribute("data-theme", name); }
export function currentTheme() { return document.documentElement.getAttribute("data-theme") || "pmoves-armor"; }
export function toggleTheme(a = "pmoves-armor", b = "darkxside-skin") {
  setTheme(currentTheme() === a ? b : a);
}

// DL-3 — persona accent-override layer.
const PERSONA_VARS = ["--pm-accent", "--pm-accent-soft", "--pm-accent-2"];

// Latest-wins guard: rapid persona changes (dropdown spam, ?agent= + a click)
// can resolve their fetches out of order; only the newest request may paint.
let personaSeq = 0;

/** Apply an accent-family override from a gateway theme object onto a root element. */
export function applyPersonaThemeToRoot(theme, root = document.documentElement) {
  const vars = personaThemeVars(theme);
  for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v);
  return vars;
}

/** Remove the persona override, reverting to the base theme's accents. */
export function clearPersona(root = document.documentElement) {
  for (const k of PERSONA_VARS) root.style.removeProperty(k);
}

/** Resolve an agent id -> gateway theme -> applied accent override. Latest call wins. */
export async function setPersona(id, opts = {}) {
  const root = opts.root || document.documentElement;
  const seq = ++personaSeq;
  const theme = await fetchAgentTheme(id, opts);
  if (seq !== personaSeq) return null; // a newer setPersona superseded this one
  return applyPersonaThemeToRoot(theme, root);
}
