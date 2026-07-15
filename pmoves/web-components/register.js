// PMOVES Web Components registry — A2UI v0.1
// Imports all registered components and calls customElements.define for each.
//
// Usage in the renderer:
//   import '/pmoves/web-components/register.js';
//
// Adding a new component to the registry? Just import it here —
// customElements.define is idempotent (browsers throw on re-registration, but
// we use a try/catch to make the import side-effect safe).

// v0.1 shipped components
import './pm-space-agent-card/pm-space-agent-card.js';
import './pm-project-card/pm-project-card.js';
import './pm-metric-tile/pm-metric-tile.js';

// v0.1 planned (not yet shipped):
// import './pm-timeline/pm-timeline.js';
// import './pm-voice-clip/pm-voice-clip.js';
// import './pm-image/pm-image.js';
// import './pm-quote-block/pm-quote-block.js';
