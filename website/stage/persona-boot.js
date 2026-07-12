// website/stage/persona-boot.js — DL-4.2 stage glue (site-specific, mirrors
// /persona/boot.js). ?agent=<id>[&alter=<name>] resolves the agent's registry
// accent via the BoTZ Gateway (loopback :8054) and overlays the --pm-* accent
// family directly — the stage runs on armor tokens, so no CF adapter is needed.
// personaThemeVars() never emits --pm-signature (reserved ✦ crimson).
//
// No query param -> no fetch, no override, no Showtime loop: public visitors
// keep the shipped accents and never open a connection to loopback.
import { resolvePersonaFromURL, personaThemeVars } from "/persona/persona-theme.js";
import { fetchAgentTheme } from "/persona/persona-resolver.js";
import { watchShowtime, applyStage } from "/persona/showtime-live.js";

const persona = resolvePersonaFromURL(window.location.search);
if (persona) {
  fetchAgentTheme(persona.id, { alter: persona.alter, ...(persona.gw ? { gw: persona.gw } : {}) })
    .then((theme) => {
      const vars = personaThemeVars(theme);
      for (const [name, value] of Object.entries(vars)) {
        document.documentElement.style.setProperty(name, value);
      }
    })
    .catch((err) => console.warn("[stage] persona resolve failed (armor accents kept):", err.message));

  // Showtime live-flip: sets <html data-stage="live">; stage.css lights the badge.
  watchShowtime({
    onState: (stage) => applyStage(stage),
    onError: () => {},
  });
}
