# Vendored `@chenglou/pretext`

Build-once-commit copy of the pretext text-layout library, consumed by
`a2ui-renderer` as a `file:` dependency. **Do not edit `dist/` by hand** — it is
compiler output. Change the fork, rebuild, re-commit.

- **License:** MIT (see `LICENSE`, retained as the license requires)
- **Upstream:** https://github.com/chenglou/pretext
- **Fork tracked by PMOVES:** `POWERFULMOVES/Pmoves-pretext` (submodule `Pmoves-pretext`)
- **Source commit:** `ac49b09b7d83ede19581fa94a8b892b07d309baf` (`v0.0.8-12-gac49b09`)
- **Upstream version at that commit:** `0.0.8`

## Why vendored rather than installed from npm

Two constraints in this service make a plain npm dependency on the *fork* impossible:

1. The Docker build context is `pmoves/`, and the `Pmoves-pretext` submodule sits at the
   **repository root** — outside the context, so a `file:` path pointing at it is unreachable
   from inside the image.
2. The builder stage runs `npm ci --ignore-scripts`, which would skip pretext's `prepack`
   (`tsc -p tsconfig.build.json`), so the `dist/` its `main` field points at would never be
   produced.

Committing the built output sidesteps both: no build script has to run, and the package lives
inside the build context.

It also removes a real hazard. Previously the service installed `@chenglou/pretext@^0.0.6`
from the registry while the repo tracked the fork at a commit 7 ahead of the `v0.0.6` tag —
different code under the same version string, with nothing to reveal the difference. Pretext
determines **layout geometry**, so a silent change there moves every line break in every
rendered frame.

## ESM boundary — do not flatten this into the service tree

`a2ui-renderer` compiles to **CommonJS** (`"module": "commonjs"`, no `"type": "module"`).
Pretext is **pure ESM**. This works because Node 24 supports `require()` of ESM.

That only holds while pretext keeps its own package boundary — this directory's
`package.json` declaring `"type": "module"`. If the files were copied loose into `src/` and
imported relatively, Node would resolve them under the service's CommonJS scope and fail to
parse the ESM syntax. Keep the nested package.

## Rebuild recipe

From the repository root, with the submodule initialized:

```bash
cd Pmoves-pretext
git fetch upstream                     # remote: https://github.com/chenglou/pretext.git
git checkout <target-commit>
npx -y -p typescript@5.9 tsc -p tsconfig.build.json

DST=../pmoves/services/a2ui-renderer/vendor/pretext
rm -rf "$DST/dist"
find dist -type f ! -name '*.map' | while read f; do
  mkdir -p "$DST/$(dirname "$f")" && cp "$f" "$DST/$f"
done
cp LICENSE "$DST/LICENSE"
```

`.map` files are excluded deliberately: their `sources` point at `src/`, which is not
vendored, so they would resolve to nothing.

Then update `version` and **Source commit** above, bump the `Pmoves-pretext` gitlink to the
same commit, and rebuild the image:

```bash
docker build --target builder -f pmoves/services/a2ui-renderer/Dockerfile pmoves/
```

## Verifying a rebuild changed nothing unexpected

Pretext ships its own accuracy harness (`accuracy/`, `corpora/`, `bun run corpus-check`),
which measures its layout against the browsers' own font engines. If a bump changes rendered
output, that harness — not this directory — is where to find out why.
