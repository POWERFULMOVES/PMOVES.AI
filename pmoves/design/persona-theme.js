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

// Only a loopback gateway may be supplied via ?gw= — the value becomes a fetch
// base URL whose JSON is reflected into --pm-* props, so an arbitrary host would
// be an injection vector. Dev-testing knob stays useful; cross-origin is blocked.
const TRUSTED_GW = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;

/** Parse ?agent=<id>&alter=<name>&gw=<url> -> {id, alter, gw} | null. gw is null unless loopback. */
export function resolvePersonaFromURL(search) {
  const p = new URLSearchParams(search || "");
  const id = p.get("agent");
  if (!id) return null;
  const gw = p.get("gw");
  return { id, alter: p.get("alter") || null, gw: gw && TRUSTED_GW.test(gw) ? gw : null };
}

/** Showtime event (or bare state string) -> "live" | null. */
export function stageFromShowtimeEvent(evt) {
  const state = typeof evt === "string" ? evt : evt && evt.state;
  return state === "showtime" ? "live" : null;
}

/** Map a signature's alters -> [{value, label}] for a picker. value matches the gateway /alter/{name} route. */
export function alterOptions(signature) {
  const alters = (signature && signature.alters) || [];
  return alters.map((a) => ({
    value: a.name || a.id || a.display_name,
    label: a.display_name || a.name || a.id,
  }));
}
