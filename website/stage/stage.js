// DL-4.1 — rooms-on-a-stage: render the baked A2UI surface with the real
// @a2ui/lit renderer. The data file is a ServerToClientMessage array, byte-
// identical to what an agent could stream over the A2UI NATS Bridge, so this
// mount path is already the spawnable-UI path (DL-4 spec D2).

import { v0_8, themeContext, ContextProvider } from "./vendor/a2ui.mjs";

// A2UI themes are per-component maps of renderer utility classes. We leave the
// class maps empty and style through two CSP-safe channels instead:
//  - inherited properties (font, color) cascade into the shadow roots from
//    stage.css --pm-* tokens on the host;
//  - additionalStyles inline-style maps (applied via Lit styleMap → CSSOM,
//    not style attributes, so no 'unsafe-inline' needed) carry the armor
//    surface treatment on Cards.
const theme = {
  additionalStyles: {
    Card: {
      background: "var(--pm-surface)",
      border: "1px solid var(--pm-border-subtle)",
      "border-radius": "var(--pm-radius)",
      padding: "var(--pm-space-lg)",
    },
  },
  components: {
    AudioPlayer: {},
    Button: {},
    Card: {},
    CheckBox: { element: {}, label: {}, container: {} },
    Column: {},
    DateTimeInput: { container: {}, label: {}, element: {} },
    Divider: {},
    Image: {
      all: {},
      avatar: {},
      header: {},
      icon: {},
      largeFeature: {},
      mediumFeature: {},
      smallFeature: {},
    },
    Icon: {},
    List: {},
    Modal: { backdrop: {}, element: {} },
    MultipleChoice: { container: {}, label: {}, element: {} },
    Row: {},
    Slider: { container: {}, label: {}, element: {} },
    Tabs: { container: {}, controls: { all: {}, selected: {} }, element: {} },
    Text: { all: {}, h1: {}, h2: {}, h3: {}, h4: {}, h5: {}, body: {}, caption: {} },
    TextField: { container: {}, label: {}, element: {} },
    Video: {},
  },
  elements: {
    a: {},
    audio: {},
    body: {},
    button: {},
    h1: {},
    h2: {},
    h3: {},
    h4: {},
    h5: {},
    iframe: {},
    input: {},
    p: {},
    pre: {},
    textarea: {},
    video: {},
  },
  markdown: {
    p: [],
    h1: [],
    h2: [],
    h3: [],
    h4: [],
    h5: [],
    ul: [],
    ol: [],
    li: [],
    a: [],
    strong: [],
    em: [],
  },
};

async function boot() {
  const host = document.getElementById("stage-surfaces");
  if (!host) return;

  // Imperative context provider: a2ui components @consume the theme from any
  // DOM ancestor — no Lit host element needed on our side.
  new ContextProvider(host, { context: themeContext, initialValue: theme });

  let messages;
  try {
    const res = await fetch("./data/public-rooms.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    messages = await res.json();
  } catch (err) {
    host.textContent = "Stage data unavailable.";
    console.error("[stage] failed to load surface data:", err);
    return;
  }

  const processor = v0_8.Data.createSignalA2uiMessageProcessor();
  processor.processMessages(messages);

  for (const [surfaceId, surface] of processor.getSurfaces()) {
    const el = document.createElement("a2ui-surface");
    el.surfaceId = surfaceId;
    el.surface = surface;
    el.processor = processor;
    el.enableCustomElements = false;
    host.appendChild(el);
  }

  installEnterRoomHandler(host);
}

// Enter-room action handler (openroom-adapter lane, 2026-07-24).
//
// Each public room card on /stage/ has a primary Button whose action is
// {name: "enter-room", context: [{key: "room_id", value: ...},
//                                  {key: "url", value: <openroom url>}]}
// — see pmoves/design/stage_data.py. The A2UI v0.8 renderer doesn't auto-route
// button actions; the spec is renderer-agnostic and leaves routing to the host
// page. We attach a single delegated click listener that walks up the DOM
// from any clicked element, looks for the nearest <a2ui-button>'s .action
// property, and navigates if the action is "enter-room".
//
// Stays in the same CSP-safe / no-inline-script spirit as the rest of the
// /stage/ surface: this is the host page's own listener, not an inline
// handler in a baked message.
function installEnterRoomHandler(host) {
  host.addEventListener("click", (event) => {
    const path = event.composedPath ? event.composedPath() : [];
    let target = null;
    for (const node of path) {
      if (node && node.tagName && node.tagName.toLowerCase() === "a2ui-button") {
        target = node;
        break;
      }
    }
    if (!target || !target.action) return;
    const action = target.action;
    if (!action || action.name !== "enter-room") return;
    const ctx = {};
    if (Array.isArray(action.context)) {
      for (const entry of action.context) {
        if (!entry || !entry.key) continue;
        const v = entry.value || {};
        if (typeof v.literalString === "string") ctx[entry.key] = v.literalString;
        else if (typeof v.literalNumber === "number") ctx[entry.key] = v.literalNumber;
        else if (typeof v.literalBoolean === "boolean") ctx[entry.key] = v.literalBoolean;
      }
    }
    const url = ctx.url;
    const roomId = ctx.room_id;
    if (!url) {
      console.warn("[stage] enter-room action missing url context; ignoring", roomId);
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    // Same-tab navigation; the OpenRoom shell mounts at ?room=<id> and the
    // shell's loader (apps/webuiapps/src/pages/RoomLoader/) takes over.
    window.location.assign(url);
  });
}

boot();
