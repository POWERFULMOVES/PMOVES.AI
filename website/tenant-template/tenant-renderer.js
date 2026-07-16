// PMOVES tenant page renderer
// Per A2UI v0.1 spec: takes a composed A2UI message stream, creates the
// corresponding web components, applies persona theming.
//
// Usage:
//   import { renderTenant } from './tenant-renderer.js';
//   await renderTenant('fordham-hill');
//
// The message stream is the output of `pmoves.tools.compose.compose_tenant_page`.
// Components come from the A2UI v0.1 registry at /pmoves/web-components/.

const A2UI_VERSION = "0.1";  // must match pmoves/tools/compose/compose.py

let _registered = false;

async function ensureRegistered() {
  if (_registered) return;
  // Dynamic import the registry (path is repo-relative when served from /).
  // In a CF Pages deploy, the web-components folder is also at the repo root.
  await import('../../pmoves/web-components/register.js');
  _registered = true;
}

function applyProps(el, props) {
  // Only props the component declares via observedAttributes may be applied.
  // The compose tool validates upstream, but composed JSON reaches this
  // renderer without it — so the component contract is the runtime boundary.
  // Anything undeclared (innerHTML, onclick, src on a non-registry element…)
  // is dropped, never written onto the live element.
  const declared = new Set(el.constructor.observedAttributes || []);
  for (const [key, value] of Object.entries(props || {})) {
    const attr = key.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`);
    if (!declared.has(attr)) {
      console.warn(`[a2ui] dropping undeclared prop "${key}" on <${el.localName}>`);
      continue;
    }
    try {
      el[key] = value;
    } catch (_) {
      // Fall back to setAttribute (kebab-case) when the property isn't defined.
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

export async function renderTenant(tenantId) {
  // Tenant ids are slugs; anything else (../, absolute paths, %-escapes)
  // would let ?tenant= fetch and render arbitrary same-origin JSON.
  if (!/^[a-z0-9][a-z0-9-]*$/.test(tenantId || '')) {
    throw new Error(`invalid tenant id: ${tenantId}`);
  }
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
      // Registry components only: a composed message must never be able to
      // instantiate <script>, <iframe>, or any other non-A2UI element.
      const tag = String(msg.component).toLowerCase();
      if (!tag.startsWith('pm-') || !customElements.get(tag)) {
        console.warn(`[a2ui] skipping non-registry component "${msg.component}"`);
        continue;
      }
      const el = document.createElement(tag);
      applyProps(el, msg.props);
      surface.appendChild(el);
    } else {
      // v0.2 messages: dataBinding, updateProps, removeComponent, etc.
      // v0.1 silently ignores unknown message types.
    }
  }
}

// Auto-run if loaded directly (no import) — the index.html uses import
// but this lets a tenant page be a single self-contained file in the future.
if (typeof window !== 'undefined' && window.location?.search?.includes('auto=1')) {
  const params = new URLSearchParams(window.location.search);
  const tenant = params.get('tenant') || 'fordham-hill';
  renderTenant(tenant).catch(console.error);
}
