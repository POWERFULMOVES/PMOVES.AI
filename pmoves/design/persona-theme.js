// pmoves/design/persona-theme.js — pure, DOM-free helpers for the persona resolver.
// Overrides the ACCENT FAMILY only. --pm-signature (reserved ✦ crimson) is never touched.

/** Map a gateway theme object -> the --pm-* custom properties to override. */
export function personaThemeVars(theme) {
  if (!theme || typeof theme !== "object") return {};
  const out = {};
  if (theme.color) out["--pm-accent"] = theme.color;
  if (theme.accent) {
    out["--pm-accent-soft"] = theme.accent;
    out["--pm-accent-2"] = theme.accent;
  }
  return out;
}

/** Parse ?agent=<id>&alter=<name>&gw=<url> -> {id, alter, gw} | null. */
export function resolvePersonaFromURL(search) {
  const p = new URLSearchParams(search || "");
  const id = p.get("agent");
  if (!id) return null;
  return { id, alter: p.get("alter") || null, gw: p.get("gw") || null };
}
