// PMOVES tenant page renderer
// Per A2UI v0.1 + v0.2 spec: takes a composed A2UI message stream, creates
// the corresponding web components, applies persona theming, wires
// v0.2 `on-<event>` attributes between components.
//
// Usage:
//   import { renderTenant } from './tenant-renderer.js';
//   await renderTenant('fordham-hill');
//
// The message stream is the output of `pmoves.tools.compose.compose_tenant_page`.
// Components come from the A2UI v0.1 + v0.2 registry at /pmoves/web-components/.

const A2UI_VERSION = "0.2";  // must match pmoves/tools/compose/compose.py

// v0.2 event wires may only invoke methods on this allowlist. Without it,
// `target[method](arg)` would let tenant JSON invoke ANY function-valued
// property on any element by id (e.g. remove, click, a DOM API). Today the
// only legitimate wired methods are pm-toast.show and pm-haptic.pulse.
const ALLOWED_METHODS = new Set(['show', 'pulse']);

let _registered = false;
let _eventWires = [];  // v0.2: list of {source, event, target, method}

async function ensureRegistered() {
  if (_registered) return;
  await import('../../pmoves/web-components/register.js');
  _registered = true;
}

function applyProps(el, props) {
  for (const [key, value] of Object.entries(props || {})) {
    try {
      el[key] = value;
    } catch (_) {
      const attr = key.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`);
      el.setAttribute(attr, String(value));
    }
  }
}

function applyTheme(theme) {
  if (!theme || theme === 'custom') return;
  document.documentElement.setAttribute('data-theme', theme);
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#050508');
}

function applyMeta(meta) {
  if (!meta) return;
  if (meta.title) {
    document.title = `${meta.title} — PMOVES`;
  }
}

function applyHeader(header) {
  if (!header) return;
  const titleEl = document.getElementById('tenant-title');
  const taglineEl = document.getElementById('tenant-tagline');
  if (header.title) titleEl.textContent = header.title;
  if (header.tagline) taglineEl.textContent = header.tagline;
}

// v0.2 event wire (A2UI v0.2 §4.3):
//   on-<event-name>="<component-id>:<method-name>"
// Scans all elements for `on-*` attributes and wires them after all
// components are mounted (so the target is guaranteed to exist).
function wireEvents() {
  _eventWires = [];
  // Scan EVERY element in the surface (including those inside shadow roots
  // we can't introspect — but `on-*` is an attribute we set, so it's on the
  // host element).
  const surface = document.getElementById('tenant-surface');
  for (const el of surface.querySelectorAll('*')) {
    for (const attr of el.getAttributeNames()) {
      if (!attr.startsWith('on-')) continue;
      if (attr === 'on-vote-cast' || attr === 'on-quorum-reached' || attr === 'on-ballot-closed') {
        const event = attr.slice(3);  // 'vote-cast' etc.
        const value = el.getAttribute(attr);
        const [targetId, method] = value.split(':');
        if (!targetId || !method) {
          console.warn(`pm-renderer: malformed event wire "${attr}='${value}'" (want "id:method")`);
          continue;
        }
        if (!ALLOWED_METHODS.has(method)) {
          console.warn(`pm-renderer: method "${method}" is not allow-listed for event wiring; skipping "${attr}='${value}'"`);
          continue;
        }
        el.addEventListener(event, (ev) => {
          const target = document.getElementById(targetId);
          if (!target) {
            console.warn(`pm-renderer: event target #${targetId} not found`);
            return;
          }
          if (typeof target[method] !== 'function') {
            console.warn(`pm-renderer: event target #${targetId}.${method} is not a function`);
            return;
          }
          // Pass the event detail (or the first arg as a string) to the method.
          const arg = ev.detail?.receipt
            ? `${ev.detail.receipt.choice.toUpperCase()} — your receipt is signed.`
            : JSON.stringify(ev.detail);
          target[method](arg);
        });
        _eventWires.push({ source: el, event, targetId, method });
      }
    }
  }
}

export async function renderTenant(tenantId) {
  await ensureRegistered();

  const url = `./data/${tenantId}.json`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} fetching ${url}`);
  }
  const payload = await resp.json();

  if (payload.a2uiVersion && payload.a2uiVersion !== A2UI_VERSION) {
    console.warn(
      `tenant ${tenantId} uses A2UI v${payload.a2uiVersion}; this renderer speaks v${A2UI_VERSION}`
    );
  }

  applyMeta(payload.tenant);
  applyTheme(payload.tenant?.theme);
  applyHeader({ title: payload.tenant?.name, tagline: payload.tenant?.tagline });

  const surface = document.getElementById('tenant-surface');
  surface.innerHTML = '';

  for (const msg of payload.messages || []) {
    if (msg.type === 'pageMeta') {
      applyTheme(msg.tenant?.theme);
    } else if (msg.type === 'pageHeader') {
      applyHeader(msg);
    } else if (msg.type === 'createComponent' && msg.component) {
      const el = document.createElement(msg.component);
      // Assign an id if the props include one (for v0.2 event-wire targeting)
      if (msg.props && msg.props.id) el.id = msg.props.id;
      applyProps(el, msg.props);
      surface.appendChild(el);
    } else {
      // v0.2 messages: dataBinding, updateProps, removeComponent, etc.
      // v0.1 silently ignores unknown message types.
    }
  }

  // Wire v0.2 events AFTER all components are mounted.
  wireEvents();
}

// Auto-run if loaded directly (no import) — the index.html uses import
// but this lets a tenant page be a single self-contained file in the future.
if (typeof window !== 'undefined' && window.location?.search?.includes('auto=1')) {
  const params = new URLSearchParams(window.location.search);
  const tenant = params.get('tenant') || 'fordham-hill';
  renderTenant(tenant).catch(console.error);
}
