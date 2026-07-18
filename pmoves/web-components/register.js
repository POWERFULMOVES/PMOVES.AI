// PMOVES Web Components registry — A2UI v0.1
// Imports all registered components and calls customElements.define for each.
//
// Usage in the renderer:
//   import '/pmoves/web-components/register.js';
//
// Adding a new component to the registry? Just import it here.
// Re-registration is prevented by ES-module caching (each module body runs
// once per realm) — customElements.define itself is NOT idempotent and
// throws on a duplicate name, so never define the same tag outside its module.

// v0.1 shipped components (7 visual + 1 haptic)
import './pm-space-agent-card/pm-space-agent-card.js';
import './pm-project-card/pm-project-card.js';
import './pm-metric-tile/pm-metric-tile.js';
import './pm-timeline/pm-timeline.js';
import './pm-voice-clip/pm-voice-clip.js';
import './pm-image/pm-image.js';
import './pm-quote-block/pm-quote-block.js';
import './pm-haptic/pm-haptic.js';  // no visible DOM, haptic output only
