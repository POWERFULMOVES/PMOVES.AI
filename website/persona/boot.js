// website/persona/boot.js — DL-3.3 site glue (NOT vendored; site-specific).
// Persona-adaptive accents for the CF marketing site: ?agent=<id>[&alter=<name>]
// resolves the agent's registry accent via the BoTZ Gateway and overlays it onto
// the site's --c-* brand layer. No query param -> this module does nothing
// (spec D5: no fetch, no override, public visitors keep the shipped accents).
//
// The gateway + Showtime are loopback services (:8054 / :9225) — this is an
// on-net demo affordance. persona-theme.js only trusts loopback ?gw= overrides,
// and the root CSP allows connect-src to those loopback origins only.
import { resolvePersonaFromURL } from "./persona-theme.js";
import { fetchAgentTheme } from "./persona-resolver.js";
import { applyCfPersonaTheme } from "./surface-cf.js";
import { watchShowtime, applyStage } from "./showtime-live.js";

const persona = resolvePersonaFromURL(window.location.search);
if (persona) {
  fetchAgentTheme(persona.id, { alter: persona.alter, ...(persona.gw ? { gw: persona.gw } : {}) })
    .then((theme) => applyCfPersonaTheme(theme))
    .catch((err) => console.warn("[persona] theme resolve failed (base accents kept):", err.message));

  // Showtime live-flip (spec D4): only watched when a persona is active, so
  // ordinary visitors never open an SSE/poll loop against loopback.
  watchShowtime({
    onState: (stage) => applyStage(stage),
    onError: () => {}, // watchShowtime falls back to /health/all polling internally
  });
}
