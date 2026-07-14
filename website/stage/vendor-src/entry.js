// Bundle entry for website/stage/vendor/a2ui.mjs (DL-4.1).
//
// Re-exports the minimal @a2ui/lit surface the stage page needs. Paths are
// relative into the PMOVES-A2UI submodule so esbuild resolves lit/@lit deps
// from the submodule's own node_modules — the website tree has none.
//
// Rebuild recipe (build-once-commit): see ../vendor/README.md.

export { v0_8 } from "../../../PMOVES-A2UI/renderers/lit/dist/src/index.js";
export { themeContext } from "../../../PMOVES-A2UI/renderers/lit/dist/src/0.8/ui/context/theme.js";
export { ContextProvider } from "../../../PMOVES-A2UI/renderers/lit/node_modules/@lit/context/index.js";
