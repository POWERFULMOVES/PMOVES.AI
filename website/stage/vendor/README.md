# /stage/ vendored A2UI bundle

`a2ui.mjs` is a build-once-commit ESM bundle of the `@a2ui/lit` renderer
(Apache-2.0, Google LLC) from the `PMOVES-A2UI` submodule, plus `@lit/context`.
It is fully self-contained: no CDN hosts, no `eval`/`new Function` (verified at
build time), safe under the strict `/stage/*` CSP in `website/_headers`.

- **Source submodule commit:** `PMOVES-A2UI @ 2d961ba2dbb05e03099883d249d6df55600d67ee`
- **Entry source:** `../vendor-src/entry.js` (documents the exported surface)
- **Exports:** `v0_8` (processor + component registration; importing the bundle
  defines the `a2ui-surface`/`a2ui-root` custom elements), `themeContext`,
  `ContextProvider`

## Rebuild recipe

Wireit's `copy-spec` scripts fail under cmd.exe on Windows — run the copy step
manually in Git Bash, then invoke `tsc` directly. Build `web_core` before `lit`
(the lit build resolves `@a2ui/web_core/*` from its sibling's `dist/`).

```bash
cd PMOVES-A2UI/renderers/web_core
npm ci
mkdir -p src/0.8/schemas && cp ../../specification/v0_8/json/*.json src/0.8/schemas
npx tsc -b

cd ../lit
npm ci
mkdir -p src/0.8/schemas && cp ../../specification/v0_8/json/*.json src/0.8/schemas
npx tsc -b

# Bundle from inside renderers/lit so bare imports (lit, @lit/context)
# resolve from the submodule's node_modules:
printf '%s\n' \
  'export { v0_8 } from "./dist/src/index.js";' \
  'export { themeContext } from "./dist/src/0.8/ui/context/theme.js";' \
  'export { ContextProvider } from "@lit/context";' > stage-entry.tmp.js
npx esbuild stage-entry.tmp.js --bundle --format=esm --minify \
  --outfile=../../../website/stage/vendor/a2ui.mjs
rm stage-entry.tmp.js
```

After rebuilding, re-run the CSP greps and update the source commit above:

```bash
grep -c "eval(" a2ui.mjs            # must be 0
grep -oE "https?://[a-z0-9.-]+" a2ui.mjs | sort -u   # license/error strings only
```
