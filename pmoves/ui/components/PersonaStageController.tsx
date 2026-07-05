"use client";

// PersonaStageController (DL-3.2) — a side-effect-only controller that wires the
// vendored DL-3 design engine into the Notebook:
//   1. On mount, resolve ?agent=<id> from the URL and overlay that persona's
//      accent family via the BoTZ Gateway (best-effort; a gateway-offline must
//      never crash Notebook — the persona overlay simply doesn't paint).
//   2. Subscribe to Showtime (:9225) SSE and flip documentElement[data-stage] to
//      "live" on the all-green frame, surfacing the state to an optional parent.
// Renders null — all DOM work happens inside useEffect (SSR-safe).
import { useEffect } from "react";
import { setPersona } from "@/lib/persona/theme-provider.js";
import { resolvePersonaFromURL } from "@/lib/persona/persona-theme.js";
import { watchShowtime, applyStage } from "@/lib/persona/showtime-live.js";
import { uiConfig } from "@/config";

export type PersonaStageControllerProps = {
  /** BoTZ Gateway base URL for the persona accent-override fetch. */
  gatewayUrl?: string;
  /** Showtime base URL for the SSE live-flip feed. */
  showtimeUrl?: string;
  /** Injectable fetch (tests / SSR-safe wiring) forwarded into setPersona. */
  fetchImpl?: typeof fetch;
  /** Injectable EventSource (tests) forwarded into watchShowtime. */
  eventSourceImpl?: unknown;
  /** Notified when the stage flips live/offline so a parent can render a badge. */
  onLive?: (live: boolean) => void;
  /** URL search string (defaults to window.location.search) — lets tests inject ?agent=. */
  search?: string;
};

export function PersonaStageController({
  gatewayUrl = uiConfig.botzGatewayUrl,
  showtimeUrl = uiConfig.showtimeUrl,
  fetchImpl,
  eventSourceImpl,
  onLive,
  search,
}: PersonaStageControllerProps) {
  useEffect(() => {
    // window/document are only touched here — useEffect never runs on the server.
    const searchStr =
      search ?? (typeof window !== "undefined" ? window.location.search : "");

    // 1) Persona accent overlay (best-effort; swallow gateway-offline errors).
    const persona = resolvePersonaFromURL(searchStr);
    if (persona?.id) {
      void setPersona(persona.id, {
        alter: persona.alter ?? undefined,
        gw: gatewayUrl,
        fetchImpl,
      }).catch(() => {
        /* gateway offline — Notebook must not crash; overlay simply doesn't paint */
      });
    }

    // 2) Showtime live-flip subscription.
    const handle = watchShowtime({
      gw: showtimeUrl,
      EventSourceImpl: eventSourceImpl,
      onState: (s) => {
        applyStage(s);
        onLive?.(s === "live");
      },
      onError: () => {
        /* broken feed — engine falls back to poll internally */
      },
    });

    return () => handle.close();
    // Run-once controller: props are captured on mount by design.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

export default PersonaStageController;
