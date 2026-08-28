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

  // P3 (openroom-realization slice 2): the room cards emit an `a2ui.action`
  // event with name="openroom.enter" and context.room_id when the Enter
  // button is clicked. We catch the event on the surface host (which is an
  // ancestor of every a2ui-surface child) and navigate to
  // `${OPENROOM_BASE_URL}/?room=<room_id>`. OPENROOM_BASE_URL is set via
  // <meta name="pmoves-openroom-base-url"> in index.html (defaults to
  // http://localhost:5173/webuiapps/ for local dev).
  const openroomBaseUrl =
    document
      .querySelector('meta[name="pmoves-openroom-base-url"]')
      ?.getAttribute("content")
      ?.trim()
      ?.replace(/\/+$/, "") || "http://localhost:5173/webuiapps";

  host.addEventListener("a2ui.action", (ev) => {
    const action = ev.detail?.action;
    if (!action || action.name !== "openroom.enter") return;
    const roomIdCtx = (action.context || []).find((c) => c.key === "room_id");
    const roomId = roomIdCtx?.value?.literalString;
    if (!roomId) {
      console.warn("[stage] openroom.enter without room_id context", action);
      return;
    }
    const target = `${openroomBaseUrl}/?room=${encodeURIComponent(roomId)}`;
    // Defensive: validate the room id matches the A2UI adapter's contract
    // (room_adapter.ts getRoomIdFromUrl() allows [a-z0-9._-]).
    if (!/^[a-z0-9._-]+$/i.test(roomId)) {
      console.warn("[stage] refusing to navigate to suspicious room id", roomId);
      return;
    }
    window.location.assign(target);
  });

  for (const [surfaceId, surface] of processor.getSurfaces()) {
    const el = document.createElement("a2ui-surface");
    el.surfaceId = surfaceId;
    el.surface = surface;
    el.processor = processor;
    el.enableCustomElements = false;
    host.appendChild(el);
  }
}

boot();
