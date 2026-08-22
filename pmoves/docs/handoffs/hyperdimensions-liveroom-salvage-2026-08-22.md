# Handoff → Crush: the Hyperdimensions viewer has been ignoring its own URL contract

**From:** z890-claude · **To:** Crush · **Date:** 2026-08-22
**Branch:** `salvage/liveroom-saveurl-from-z890-worktree` on `POWERFULMOVES/Pmoves-hyperdimensions`
**Change class:** `submodule:` + `service-contract:`

---

## The headline

This started as "four months of uncommitted work found in a dirty submodule." It
is not that. **It is the missing client half of a contract the gateway already
depends on, and a room healthcheck is currently sitting on top of the gap.**

Three facts, each verified directly:

1. `hi-rag-gateway-v2` serves a 307 to a URL carrying three query parameters:

   ```python
   # pmoves/services/hi-rag-gateway-v2/routes/geometry.py:188-193
   @router.get("/hyperdimensions/provenance/view")
   def hyperdimensions_latest_provenance_view(_=Depends(require_tailscale)):
       return RedirectResponse(
           url="/hyperdimensions/app/?saveUrl=/hyperdimensions/provenance/latest.json"
               "&fallbackSave=saves/chit_manifold.json&liveRoom=geometry",
           status_code=307,
       )
   ```

2. `pmoves/config/rooms/darkxsides.room.json:541` sets that exact route as the
   `hyperdimensions-viewer` app's `healthcheck_route`.

3. **The current tip of `index.html` contains zero references to `saveUrl`,
   `fallbackSave` or `liveRoom`.** It unconditionally `fetch`es
   `saves/nautilus.json` and discards all three parameters.

So the server has been redirecting to a URL whose parameters the client silently
throws away, and a room's health depends on it. The salvaged diff is the code
that reads them.

## Where the work is

Pushed to `salvage/liveroom-saveurl-from-z890-worktree`, committed **against its
original base (`5ec35cb9`), not the tip.** The tip is 14 commits ahead and a
3-way apply conflicts in `index.html` around the render loop. The base commit
keeps the diff readable; the rebase is yours because it needs someone who can
read the viewer's intent.

It was found uncommitted in a z890 working tree, dated 2026-04-28, existing in no
commit anywhere. It survived only because `git submodule update` refuses to
overwrite a dirty tree — a `--force`, used elsewhere in the same session to
repair unrelated hollow checkouts, would have destroyed it. Provenance is
unknown; it is not the committer's work.

## What it adds

| addition | purpose |
|---|---|
| `saveUrl` / `saveFile` / `fallbackSave` params | generalises the hardcoded `fetch('saves/…')` to absolute paths, `saves/`-relative, or full URLs |
| `loadStartupConfig()` | `saveUrl` → `saveFile` → `fallbackSave` → `saves/nautilus.json` |
| `connectLiveRoom()` | websocket to `/ws/signaling/<liveRoom>`, presence handshake, exponential backoff 1s→15s |
| `handleLiveRoomPayload()` | branches on `hyperdimensions.save.v1`, `load_config`, `load_config_url` |
| `window.addEventListener('message', …)` | same shapes over `postMessage`, for iframe embedding |

**The protocol already matches.** The server sends client relays wrapped as
`{"room": …, "relay": …}` (`geometry.py:534`) and its own broadcasts unwrapped as
`{"type": "hyperdimensions.save.v1", …}` (`geometry_bus.py:444-454`). The
salvaged handler branches on exactly those two shapes. There is no mismatch to
reconcile.

The dossier edit (`PMOVES.AI_INTEGRATION.md`) fills in fields that were `_TBD_`
and already *documented* this live-refresh path. The doc was ahead of the code;
this closes the gap.

---

## Reconciliation with the four adjacent efforts

Checked each for collision. **Three are clean; the risk is vocabulary, not code.**

### Beat analyzer — no collision, it is upstream

`pmoves/tools/analyze_beats.py` (librosa + ffmpeg) feeds
`pmoves/tools/beats_to_cgp.py`, which maps sonic fields onto the CHIT state
vector — `tempo_bpm → delta`, `spectral_centroid → Hz`, `loudness_LRA → kappa`,
`spectral_flatness → A`, `coherence_score → F` — and publishes `geometry.cgp.v1`.

It is a **producer** into the same geometry bus the viewer consumes, one layer
up. Its export target is a *different* surface: `website/embeds/beats-
constellation/tracks.json`, not the hyperdimensions viewer.

### Constellations — no collision, it is a data model

"Constellation" is not a service. It is a Pydantic model in
`pmoves/services/gateway/gateway/api/chit.py` — the cluster unit of a CGP packet,
grouped under `SuperNode`s, indexed by `ShapeStore`.

`website/embeds/beats-constellation/` is a **separate renderer** with its own
canvas code. It shares the vocabulary, not the implementation, and never loads
`Pmoves-hyperdimensions/index.html`.

### CHIT visual tour — no collision today, but read this before the reskin

Two things share the name:

- `pmoves/docs/PMOVESCHIT/VISUAL_TOUR.md` — prose documentation
- `website/chit-tour/` — the deployed tour at `chit.pmoves.ai`, whose tables are
  generated from `agent_registry.yaml` by `pmoves/scripts/gen_chit_tour_data.py`

**The tour does not embed the hyperdimensions viewer at all.** Nothing to
reconcile now. But if `feat/dl-1b-chit-tour-reskin` adds a live geometry view, it
should reuse this exact `saveUrl`/`liveRoom` contract rather than invent a
second one — that contract is now implemented and is the only one there is.

### Rooms — this is where the care is needed

**"Room" means two unrelated things and this work touches both.**

- **P7 room** — the rooms-on-a-stage manifest (`ROOM_MANIFEST_CONTRACT.md`): an
  agent-owned shell with theme, panels, apps.
- **signaling room** — an arbitrary string naming a websocket broadcast group,
  e.g. `liveRoom=geometry`. Orthogonal, and older.

`darkxsides.room.json` references both: it hosts `hyperdimensions-viewer` as a P7
app (`:90-99`) whose page then opens its own `liveRoom=geometry` signalling
socket. Do not let these collapse into one word in any follow-up.

---

## Two things to resolve before generalising

**1. There are two `/ws/signaling` implementations, with different auth.**

| service | route shape | auth |
|---|---|---|
| `hi-rag-gateway-v2` (`routes/geometry.py:513-547`) | `/ws/signaling/{room}` path segment | Tailscale-IP gated (`_tailscale_ip_allowed`) |
| `gateway` (`gateway/api/signaling.py`) | `/ws/signaling?room=&peer=` query params | **no Tailscale gating found in that file** |

Same route prefix, two services, two param styles, **asymmetric auth posture**.
The salvaged client uses a relative URL, so it resolves against whatever host
serves `/hyperdimensions/app` — which is `hi-rag-gateway-v2`, the gated one. That
is the safe outcome *by accident of relative URL resolution*, not by design.

This audit did not determine which is canonical. Decide that before anything new
is pointed at "the signaling websocket", and treat the auth asymmetry as a
finding in its own right.

**2. The public mirror will go stale.**

`website/hyperdim/` is generated from the submodule by
`pmoves/tools/sync_hyperdim.py` via `make -C pmoves pmoves-ai-sync-hyperdim`
(a prerequisite of `pmoves-ai-dev` / `pmoves-ai-deploy`). It picks this up
automatically on the next sync — but a deploy *without* that target leaves the
public mirror on the old, parameter-ignoring code.

There is also a **third** control channel into the viewer:
`pmoves/chrome-extension/portal/portal.js` and the submodule's own
`portal/portal.js` post `capture_screenshot` / `start_stream` messages to a
`hyperdimensions-frame` iframe. Different `type` values, so no collision with the
salvaged `load_config` handler — but two independent `postMessage` producers now
target the same iframe. Extend one carefully.

---

## Suggested order

1. Rebase `salvage/liveroom-saveurl-from-z890-worktree` onto the tip; expect
   conflicts in `index.html` near the render loop.
2. Verify `/hyperdimensions/provenance/view` actually loads the provenance JSON
   afterwards — that is the DARKXSIDE room's healthcheck, and it is the whole
   point.
3. Run `make -C pmoves pmoves-ai-sync-hyperdim` before any deploy.
4. Answer the canonical-signaling-service question, or file it.

## Related

- `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md` — L2.5 framing
- `pmoves/config/rooms/darkxsides.room.json` — the room binding this serves
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — the *other* meaning of "room"
