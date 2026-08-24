---
name: fc-nextjs-website
description: >-
  Build, package, and deploy a Next.js SSR/SSG app on function-compute's
  "nextjs" environment — Aliyun FC custom runtime (custom.debian10, Node.js 20),
  started via `node /code/server.js` on port 9000. Use this when a user wants to
  host a Next.js app (App Router or Pages Router) on function-compute. Covers the
  `output: 'standalone'` build, the zip layout (server.js at the root), the
  platform-injected env vars, and the /functionCompute create + upload-to-LATEST
  API (a human publishes). 在 function-compute 的 "nextjs" 环境（阿里云 FC 自定义运行时
  custom.debian10，Node.js 20，用 `node /code/server.js` 启动，监听 9000 端口）上
  构建、打包并部署 Next.js SSR/SSG 应用。当用户需要在 function-compute 上托管 Next.js
  应用时使用。涵盖 `output: 'standalone'` 构建、zip 结构（server.js 在根目录）、平台注入的
  环境变量，以及创建函数与上传到 LATEST 的 API（发布由人工完成）。
---

# Deploy a Next.js app on function-compute (nextjs)
# 在 function-compute 上部署 Next.js 应用（nextjs）

## AutoClaw managed-delivery boundary (highest priority) / 受控交付边界（最高优先级）

When `website_delivery_start` or `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
is active, **do not call `/functionCompute`, read/request/store/output a JWT, or
execute this Skill's curl commands.** API sections are reference-only. Build,
package, and verify the artifact locally; AutoClaw Main owns create/upload, and
the human owns publication. The current managed automatic-preview path supports
nginx only, so do not add an nginx `autoPreview` marker for a Next.js package.

当 `website_delivery_start` 或 `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
生效时，**禁止调用 `/functionCompute`、读取/索取/保存/输出 JWT，禁止执行本 Skill 的 curl。**
API 章节仅作参考；Agent 只负责本地构建、打包与验证，创建和上传由 AutoClaw Main 负责，
正式发布由用户负责。当前自动预览仅支持 nginx，Next.js 产物不得写 nginx `autoPreview` 标记。

## 1. What this environment is / 环境说明

**English.** The `nextjs` environment runs a **Next.js standalone server** on
Aliyun Function Compute's **custom runtime** (`runtime: custom.debian10`,
Debian 10, ships **Node.js 20** at `/var/fc/lang/nodejs20/bin`). Your uploaded
zip is extracted to **`/code`**, and the platform starts the app with a fixed
command that runs **`/code/server.js`** with the bundled Node.js 20. You deploy
a `next build` **`output: 'standalone'`** build, not raw source and not a
container image.

The platform starts the container with this fixed command (set by the platform
in `CustomRuntimeConfig` — the Agent does **not** set it):

```
/var/fc/lang/nodejs20/bin/node /code/server.js
```

So your zip **must** place `server.js` at its **root** (it becomes
`/code/server.js`, matching the command). The standalone `server.js` reads
`PORT` and `HOSTNAME` from the environment (the platform injects `9000` /
`0.0.0.0`), so **do not hardcode a port**.

A freshly-created function ships a **placeholder** `server.js` (a tiny built-in
`http` server that prints "upload your standalone build"). It runs until the
Agent uploads a real standalone build.

Fixed constraints (from the environment preset — do not fight these):

| Property / 属性 | Value / 值 |
|---|---|
| FC runtime | `custom.debian10` (Debian 10, bundled Node.js 20 at `/var/fc/lang/nodejs20/bin`) |
| Start command / 启动命令 | `/var/fc/lang/nodejs20/bin/node /code/server.js` (fixed by the platform) |
| Listen port / 监听端口 | **9000** (the app must listen on 9000; FC routes here) |
| Code root / 代码目录 | **`/code`** (your zip extracts here; `server.js` → `/code/server.js`) |
| Memory / 内存 | **1024 MB** |
| vCPU | **0.5** |
| Disk / 磁盘 | 512 MB |
| Timeout / 超时 | 60 s |
| Instance concurrency / 实例并发 | **5** |
| Filesystem / 文件系统 | On FC custom runtime the whole container is writable as root; `/code` holds the code |
| Injected env vars / 注入的环境变量 | `PORT=9000`, `HOSTNAME=0.0.0.0`, `NODE_ENV=production`, `PATH=/var/fc/lang/nodejs20/bin:/usr/local/bin:/usr/bin:/bin` |

**中文.** `nextjs` 环境在阿里云函数计算的**自定义运行时**
（`runtime: custom.debian10`，Debian 10，内置 **Node.js 20**，位于
`/var/fc/lang/nodejs20/bin`）上运行 **Next.js standalone 服务器**。你上传的 zip
会被解压到 **`/code`**，平台用固定命令以内置的 Node.js 20 运行 **`/code/server.js`**。
你部署的是 `next build` 的 **`output: 'standalone'`** 产物，而不是源码，也不是容器镜像。

平台在 `CustomRuntimeConfig` 中用固定命令启动容器（**由平台设置，Agent 不设置**）：
`/var/fc/lang/nodejs20/bin/node /code/server.js`。因此你的 zip **必须**把
`server.js` 放在**根目录**（解压后为 `/code/server.js`，与启动命令匹配）。standalone
的 `server.js` 从环境变量读取 `PORT` 和 `HOSTNAME`（平台注入 `9000` / `0.0.0.0`），
所以**不要硬编码端口**。

新创建的函数自带一个**占位** `server.js`（一个用内置 `http` 模块写的小服务器，会打印
"upload your standalone build"），在 Agent 上传真正的 standalone 构建之前一直运行它。

平台注入的四个环境变量：`PORT=9000`、`HOSTNAME=0.0.0.0`、`NODE_ENV=production`、
`PATH=/var/fc/lang/nodejs20/bin:/usr/local/bin:/usr/bin:/bin`。

## 2. Build with `output: 'standalone'` / 使用 `output: 'standalone'` 构建

Next.js standalone mode produces a self-contained server: `next build` writes a
`server.js` plus a minimal `node_modules/` into `.next/standalone/`. Enable it
in `next.config.js`:

```js
// next.config.js
module.exports = {
  output: 'standalone',
};
```

Then build:

```bash
next build
```

This produces:

- `.next/standalone/` — a self-contained **`server.js`** + minimal
  **`node_modules/`** (this is the server you deploy).
- `.next/static/` — hashed static assets (JS/CSS chunks). **Not** copied into
  `standalone/` automatically — you must copy it in.
- `public/` — your static files (images, fonts, etc.). Also not copied
  automatically.

**中文.** Next.js 的 standalone 模式会产出一个自包含的服务器：`next build` 会在
`.next/standalone/` 中生成 **`server.js`** 和一份精简的 **`node_modules/`**。在
`next.config.js` 中启用 `output: 'standalone'`，然后执行 `next build`。注意
`.next/static/`（带哈希的静态资源）和 `public/`（你的静态文件）**不会**被自动复制到
`standalone/` 里，需要你手动复制进去。

## 3. The zip-layout contract / 文件结构约定

Your zip is extracted to `/code`. The **zip root** (not a nested folder) must
contain `server.js`, its `node_modules/`, and the static assets in the paths
Next.js expects — `.next/static` next to `server.js`, and `public` next to
`server.js`:

```
app.zip
├── server.js           # REQUIRED, at zip root -> /code/server.js
├── node_modules/        # from .next/standalone/node_modules
├── .next/
│   ├── static/          # copied from your build's .next/static
│   └── ...              # other files carried in by standalone
├── public/              # copied from your project's public/
└── package.json         # carried in by standalone
```

Rules / 规则:

- `server.js` **must** be at the root, because the start command runs
  `/code/server.js` literally. 必须放在根目录。
- Do **not** wrap everything in a top-level folder (e.g. `app/server.js`) —
  that would extract to `/code/app/server.js` and the start command would fail.
  不要多套一层目录。
- Keep the standalone `node_modules/` **next to** `server.js`. 保持 standalone 的
  `node_modules/` 与 `server.js` 平级。
- Place `.next/static` at `./.next/static` and `public` at `./public`, both
  relative to `server.js`. 把 `.next/static` 放到 `./.next/static`、`public` 放到
  `./public`，都相对于 `server.js`。
- **Do not** hardcode a port — `server.js` reads `PORT`/`HOSTNAME` from the
  injected env (`9000` / `0.0.0.0`). 不要硬编码端口。

## 4. Package the zip / 打包 zip

Standard recipe: assemble the standalone output plus the static and public
directories in a staging folder, then zip its **contents** so `server.js` sits
at the zip root.

```bash
# after `next build` with output: 'standalone'
rm -rf deploy && mkdir -p deploy
cp -r .next/standalone/* ./deploy/          # server.js + node_modules + package.json
cp -r .next/static ./deploy/.next/static    # hashed assets next to server.js
cp -r public ./deploy/public                # your static files (if you have a public/)
(cd deploy && zip -r ../app.zip .)          # zip the CONTENTS; server.js at root

# sanity check: server.js must appear at the TOP with no folder prefix
unzip -l app.zip

# base64 for the upload API (Linux: -w0; macOS/BSD: pipe through tr)
base64 -w0 app.zip > app.zip.b64            # Linux
# base64 app.zip | tr -d '\n' > app.zip.b64 # macOS
```

Verify the listing shows `server.js` at the root (no `deploy/` or other
prefix). 确认 `unzip -l` 输出中 `server.js` 位于根目录，没有目录前缀。

## 5. Standalone API reference — prohibited in managed delivery / 独立 API 参考——受控交付中禁止执行

All calls are under `/functionCompute` and require
`Authorization: Bearer <JWT>`. 所有调用都在 `/functionCompute` 下，需携带
`Authorization: Bearer <JWT>`。

**Deploy model / 部署模型:** create function → upload zip to **LATEST**
(served immediately at `preview_url`) → **the human clicks Publish in the UI**
to repoint the release alias so `stable_url` serves it. This sequence is
reference-only when AutoClaw managed delivery is active; Main performs it.
AutoClaw 受控交付生效时，本流程仅作参考并由 Main 执行。

### Step 1 — Create the function / 创建函数

```bash
curl -sS -X POST https://<host>/functionCompute/functions \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"environment":"nextjs","name":"my-app"}'
```

Response (note the `id`, `preview_url`, `stable_url`):

```json
{
  "function": {
    "id": "fc-1a2b3c4d",
    "environment": "nextjs",
    "region": "cn-hangzhou",
    "state": "ready",
    "released_version_id": "1",
    "stable_url": "brave-otter.<domain>",
    "preview_url": "calm-finch.<domain>"
  }
}
```

The new function already serves the **placeholder** `server.js` until you
upload a real build. Save `function.id` for the next step. `stable_url` /
`preview_url` are `<label>.<domain>` hostnames. 新函数默认运行**占位** `server.js`，
在你上传真正的构建之前一直如此；记下 `function.id`。

### Step 2 — Upload your code to LATEST / 上传代码到 LATEST

`zip_base64` is the base64 string from step 4. This overwrites LATEST and is
served **immediately** at `preview_url`.

```bash
curl -sS -X POST https://<host>/functionCompute/functions/fc-1a2b3c4d/code \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"zip_base64\":\"$(cat app.zip.b64)\"}"
```

Response:

```json
{ "uploaded": true, "preview_url": "calm-finch.<domain>" }
```

Open `https://<preview_url>/` to verify your app renders. 打开 `preview_url`
验证应用是否正常渲染。

### Step 3 — Human publishes / 人工发布

**Stop here.** Tell the user their app is live on the **preview URL** and that
they should click **Publish** in the function-compute UI to promote it to the
**stable URL**. Do not call the publish endpoint yourself. 到此为止：告知用户应用
已在 **preview 地址**可访问，请他们在界面点击 **Publish**，将其提升到 **stable 地址**。
Agent 不要自行调用发布接口。

## 6. API reference (this environment) / 接口速查

| Method & Path | Body | Purpose |
|---|---|---|
| `POST /functionCompute/functions` | `{"environment":"nextjs","name":"..."}` | Create; returns `{function:{id, environment, region, state, released_version_id, stable_url, preview_url}}` |
| `GET /functionCompute/functions` | — | List: `{items,total}` |
| `GET /functionCompute/functions/{id}` | — | Get one: `{function}` |
| `POST /functionCompute/functions/{id}/code` | `{"zip_base64":"..."}` | **Upload to LATEST** → served at `preview_url` (Main uses this in managed delivery) |
| `POST /functionCompute/functions/{id}/publish` | `{"description":"..."}` | Promote LATEST → release alias so `stable_url` serves it (**human only**) |
| `POST /functionCompute/functions/{id}/rollback` | `{"version_id":"N"}` | Repoint release to an older version |
| `GET /functionCompute/functions/{id}/versions` | — | `{items, current_released}` |
| `GET /functionCompute/functions/{id}/urls` | — | `{stable_url, preview_url, prefixes}` |
| `POST /functionCompute/functions/{id}/prefixes` | `{"mode":"release\|preview"}` | Allocate another `<label>.<domain>` |
| `DELETE /functionCompute/functions/{id}` | — | Delete the function |
| `GET /functionCompute/environments` | — | List environments |
| `GET /functionCompute/environments/nextjs/guide` | — | This guide (raw markdown) |

## 7. Troubleshooting / 排错

- **502 / not starting.** The app didn't start on port 9000. Ensure you shipped
  the standalone `server.js` (it reads `PORT`/`HOSTNAME` from env — do not
  hardcode) and that `server.js` is at the zip **root** (`/code/server.js`).
  确认部署的是 standalone `server.js`（从环境变量读取 `PORT`/`HOSTNAME`，不要硬编码），
  且 `server.js` 位于 zip **根目录**（`/code/server.js`）。
- **Still shows the placeholder page.** You opened `stable_url` (only updates
  after a human publishes) — check `preview_url`, or you haven't uploaded a real
  build yet. 页面仍是占位页：你可能打开了 `stable_url`（需人工发布后才更新），请查看
  `preview_url`，或者你尚未上传真正的构建。
- **Missing CSS / JS / broken assets.** You forgot to copy `.next/static` and/or
  `public` next to `server.js`. Re-run the packaging recipe in section 4.
  样式/脚本丢失：忘记把 `.next/static` 和/或 `public` 复制到 `server.js` 旁边，重跑第 4 节的打包步骤。
- **`Cannot find module` on start.** You didn't include the standalone
  `node_modules/` (from `.next/standalone/`), or you zipped the source tree
  instead of the standalone output. Rebuild with `output: 'standalone'` and
  package `.next/standalone/*`. 启动时报找不到模块：没有包含 standalone 的
  `node_modules/`，或打包了源码而非 standalone 产物。用 `output: 'standalone'` 重新构建。
- **Start command fails / wrong path.** `server.js` was nested in a subfolder.
  Re-zip so `server.js` is at the zip root. 启动命令失败：`server.js` 被多套了一层目录，
  重新打包让它位于根目录。
- **Change not visible.** Re-check you opened `preview_url` (LATEST), not
  `stable_url`. 确认打开的是 `preview_url`（LATEST），而非 `stable_url`。
- **Wrong environment.** For a purely static site use `nginx`; for an HTTP
  handler function use `nodejs`/`python`. `nextjs` is for a Next.js standalone
  server. 需要纯静态站点请用 `nginx`；需要 HTTP handler 函数请用 `nodejs`/`python`。
