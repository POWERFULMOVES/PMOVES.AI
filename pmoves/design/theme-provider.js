// pmoves/design/theme-provider.js — dependency-free theme switch.
// DL-3 will extend setPersona() to resolve via BoTZ Gateway /v1/agent/theme/{id}.
export function setTheme(name) { document.documentElement.setAttribute("data-theme", name); }
export function currentTheme() { return document.documentElement.getAttribute("data-theme") || "pmoves-armor"; }
export function toggleTheme(a = "pmoves-armor", b = "darkxside-skin") {
  setTheme(currentTheme() === a ? b : a);
}
