# Review Dump — POWERFULMOVES/PMOVES.AI#2441

**feat(ui): persona living-doc route + user greeting + rooms null guard**

- State: `OPEN` | Branch: `feat/persona-livingdoc-rooms` → `main` | +108/-1 (4 files)
- Author: POWERFULMOVES | Collected: 2026-08-06T23:53:32.695075+00:00

## Summary

| Metric | Count |
|---|---|
| Total threads | 4 |
| Resolved | 0 |
| Open P1/P2 (actionable) | 4 |
| Committable suggestions | 0 |

**Severity breakdown:** P1=3, P2=1

## Reviews (1)

- **chatgpt-codex-connector** (COMMENTED) —  ### 💡 Codex Review  Here are some automated review suggestions for this pull request.  **Reviewed commit:** `a198e1cf3f`       <details> <summary>ℹ️ About Codex in GitHub</summary> <br/>  [Your team 

## Threads

### 1. 🔴 [P1] chatgpt-codex-connector — `pmoves/ui/app/persona/livingdoc/route.ts:36`

**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Exempt the public persona route from authentication**

For unauthenticated visitors, the checked `pmoves/ui/proxy.ts` allows only its `PUBLIC_PATHS`/prefixes and redirects this new route to `/login`; this conflicts with `persona.room.livingdoc.json`, which declares the room public and owner-only false, and with the public-edge runbook's LinkedIn-facing use case. Add `/persona/livingdoc` and its asset prefix to the proxy's public paths so the intended audience can access the route without a Supabase session or boot JWT.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,92 @@
+import fs from 'fs';
+import path from 'path';
+
+export const dynamic = 'force-dynamic';
+
+const PERSONA_DIR_CANDIDATES = [
+  path.join(process.cwd(), 'data', 'rooms', 'persona'),
+  path.join(process.cwd(), 'rooms', 'persona'),
+  path.join(process.cwd(), '..', 'rooms', 'persona'),
+];
+
+const MIME_TYPES: Record<string, string> = {
+  '.html': 'text/html; charset=utf-8',
+  '.css': 'text/css; charset=utf-8',
+  '.js': 'application/javascript; charset=utf-8',
+  '.json': 'application/json; charset=utf-8',
+  '.svg': 'image/svg+xml',
+  '.png': 'image/png',
+  '.jpg': 'image/jpeg',
+  '.woff2': 'font/woff2',
+  '.mp4': 'video/mp4',
+  '.webm': 'video/webm',
+  '.woff': 'font/woff',
+  '.ttf': 'font/ttf',
+};
+
+function resolvePersonaDir(): string | null {
+  for (const p of PERSONA_DIR_CANDIDATES) {
+    try {
+      if (fs.existsSync(p) && fs.statSync(p).isDirectory()) return p;
+    } catch { /* continue */ }
+  }
+  return null;
+}
+
+export async function GET(request: Request) {
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2441#discussion_r3730823702)

### 2. 🔴 [P1] chatgpt-codex-connector — `pmoves/ui/app/persona/livingdoc/route.ts:10`

**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Mount the persona bundle into the production UI**

In the checked Compose deployment, `pmoves-ui` builds with context `./ui` and mounts only `./config/rooms` at `/app/rooms`; the standalone image likewise copies no `pmoves/rooms/persona` content. With production `cwd` `/app`, none of these candidates therefore contains the persona directory, so every request reaches the line 38 404. Copy or mount the rendered persona bundle into the runtime and point resolution at that explicit location.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,92 @@
+import fs from 'fs';
+import path from 'path';
+
+export const dynamic = 'force-dynamic';
+
+const PERSONA_DIR_CANDIDATES = [
+  path.join(process.cwd(), 'data', 'rooms', 'persona'),
+  path.join(process.cwd(), 'rooms', 'persona'),
+  path.join(process.cwd(), '..', 'rooms', 'persona'),
+];
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2441#discussion_r3730823711)

### 3. 🔴 [P1] chatgpt-codex-connector — `pmoves/ui/app/persona/livingdoc/route.ts:57`

**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Route persona asset paths through a catch-all**

This subpath-serving branch cannot receive asset requests because `app/persona/livingdoc/route.ts` registers only the exact `/persona/livingdoc` route; the built Next route manifest confirms the exact-match regex. Moreover, from the slashless document URL, relative references such as `walkthrough.mp4` and `pretext/index.html` resolve under `/persona/`, while even `/persona/livingdoc/...` would not match this handler. Use an optional catch-all route and make the document's asset base agree with it, otherwise the walkthrough and PreTeXt surfaces return 404.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,92 @@
+import fs from 'fs';
+import path from 'path';
+
+export const dynamic = 'force-dynamic';
+
+const PERSONA_DIR_CANDIDATES = [
+  path.join(process.cwd(), 'data', 'rooms', 'persona'),
+  path.join(process.cwd(), 'rooms', 'persona'),
+  path.join(process.cwd(), '..', 'rooms', 'persona'),
+];
+
+const MIME_TYPES: Record<string, string> = {
+  '.html': 'text/html; charset=utf-8',
+  '.css': 'text/css; charset=utf-8',
+  '.js': 'application/javascript; charset=utf-8',
+  '.json': 'application/json; charset=utf-8',
+  '.svg': 'image/svg+xml',
+  '.png': 'image/png',
+  '.jpg': 'image/jpeg',
+  '.woff2': 'font/woff2',
+  '.mp4': 'video/mp4',
+  '.webm': 'video/webm',
+  '.woff': 'font/woff',
+  '.ttf': 'font/ttf',
+};
+
+function resolvePersonaDir(): string | null {
+  for (const p of PERSONA_DIR_CANDIDATES) {
+    try {
+      if (fs.existsSync(p) && fs.statSync(p).isDirectory()) return p;
+    } catch { /* continue */ }
+  }
+  return null;
+}
+
+export async function GET(request: Request) {
+  const personaDir = resolvePersonaDir();
+  if (!personaDir) {
+    return new Response('Persona room not found', { status: 404 });
+  }
+
+  const url = new URL(request.url);
+  const pathname = url.pathname;
+
+  if (pathname === '/persona/livingdoc' || pathname === '/persona/livingdoc/') {
+    const indexPath = path.join(personaDir, 'index.html');
+    try {
+      const html = fs.readFileSync(indexPath, 'utf-8');
+      return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
+    } catch {
+      return new Response('Persona index.html not found', { status: 404 });
+    }
+  }
+
+  // Serve static assets from the persona directory (pretext/, walkthrough.mp4, etc.)
+  const subPath = pathname.replace(/^\/persona\/livingdoc\//, '');
+  const requestedFile = path.join(personaDir, subPath);
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2441#discussion_r3730823715)

### 4. 🔴 [P2] chatgpt-codex-connector — `pmoves/ui/app/persona/livingdoc/route.ts:9`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Resolve the rendered persona directory**

In local development the first existing candidate is `pmoves/rooms/persona`, but `make persona-render` places the generated `walkthrough.mp4` and compiled `pretext/index.html` under the gitignored `pmoves/rooms/persona/dist` directory; the source directory contains neither artifact. Even after asset routing is corrected, this handler will select the raw source tree and report those generated files missing, so resolve `dist` first or configure the rendered bundle path explicitly.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,92 @@
+import fs from 'fs';
+import path from 'path';
+
+export const dynamic = 'force-dynamic';
+
+const PERSONA_DIR_CANDIDATES = [
+  path.join(process.cwd(), 'data', 'rooms', 'persona'),
+  path.join(process.cwd(), 'rooms', 'persona'),
+  path.join(process.cwd(), '..', 'rooms', 'persona'),
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2441#discussion_r3730823723)

