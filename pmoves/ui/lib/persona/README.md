# Vendored persona/design engine

These four `.js` files are **VENDORED verbatim** from `pmoves/design/` (the canonical
source):

- `persona-theme.js`
- `persona-resolver.js`
- `theme-provider.js`
- `showtime-live.js`

**DO NOT edit them here.** The Notebook UI (Next.js standalone) cannot import across the
`pmoves/design/*` directory boundary (`outputFileTracingRoot` is pinned to the ui dir), so
the engine is copied in-tree.

To change behavior, edit the source in `pmoves/design/` and resync:

```
make -C pmoves design-vendor
```

Drift between these copies and the canonical source is caught by:

```
make -C pmoves design-vendor-check
```

The co-located `*.d.ts` files are hand-written TypeScript declarations so the Notebook TS
can `import { setPersona } from "@/lib/persona/theme-provider.js"` and type-check.
