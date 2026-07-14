// pmoves/design/surface-cf.js — CF marketing-site (--c-*) persona adapter (DL-3.3).
// The CF site consumes a --c-* brand layer with INLINED values (website/styles.css
// does not var()-chain to --pm-*), so the shared --pm-* accent override cannot
// reach it. This adapter maps a gateway theme onto the CF layer's own accent vars.
// Accent family only — backgrounds/ink are never overridden (spec D3); the
// reserved ✦ signature is not a --c-* var, so it is untouched by construction.

/** Map a gateway theme object -> the --c-* custom properties to override. */
export function cfThemeVars(theme) {
  if (!theme || typeof theme !== "object") return {};
  const out = {};
  if (theme.color) out["--c-accent"] = theme.color;
  if (theme.accent) out["--c-accent-2"] = theme.accent;
  return out;
}

const CF_PERSONA_VARS = ["--c-accent", "--c-accent-2"];

/** Apply a CF accent override from a gateway theme object onto a root element. */
export function applyCfPersonaTheme(theme, root = document.documentElement) {
  const vars = cfThemeVars(theme);
  for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v);
  return vars;
}

/** Remove the CF persona override, reverting to the site's shipped accents. */
export function clearCfPersona(root = document.documentElement) {
  for (const k of CF_PERSONA_VARS) root.style.removeProperty(k);
}
