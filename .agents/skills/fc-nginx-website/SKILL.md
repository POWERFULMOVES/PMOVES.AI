---
name: fc-nginx-website
description: >-
  Build, package, and deploy a static website (HTML/CSS/JS/images or any
  pre-built SPA output) on the function-compute service's "nginx" environment,
  which runs Aliyun FC's custom runtime (Debian 9, built-in Nginx 1.10.3)
  serving files from /code on port 9000. Use this when a user asks to host a
  static site, landing page, docs site, or built front-end (React/Vue/Vite
  "dist", Hugo/Jekyll output) and the deploy target is function-compute with
  environment="nginx". Covers the nginx.conf contract, zip layout, and a
  reference for the Main-process-managed Function Compute delivery flow.
  在 function-compute 的 "nginx" 环境（阿里云 FC 自定义运行时，
  Debian 9，内置 Nginx 1.10.3，从 /code 提供服务，监听 9000 端口）上构建、打包并部署静态网站
  （HTML/CSS/JS/图片，或任何预构建的 SPA 产物）。当用户需要托管静态站点、落地页、文档站或已构建
  的前端（React/Vue/Vite 的 dist、Hugo/Jekyll 产物），且部署目标是 function-compute 且
  environment="nginx" 时使用本指南。涵盖 nginx.conf 约定、zip 目录结构，以及由 Main
  进程受控执行的 Function Compute 交付流程参考（发布由人工完成）。
---

# Deploy a static website on function-compute (nginx)
# 在 function-compute 上部署静态网站（nginx）

## AutoClaw managed-delivery boundary (highest priority) / 受控交付边界（最高优先级）

When `website_delivery_start` or `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
is active, this is an AutoClaw-managed delivery. **Do not call any
`/functionCompute` API, do not read/request/store/output a JWT, and do not run
the curl examples in this Skill.** Treat all API examples as protocol reference
only. Build and verify the project locally, then follow the managed protocol:
for supported nginx preview delivery, update `projects/projects.json` last and
let AutoClaw Main create/upload/publish through its controlled module. A human
owns formal publication.

当 `website_delivery_start` 或 `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
生效时，本任务属于 AutoClaw 受控交付。**禁止调用任何 `/functionCompute` API，禁止读取、
索取、保存或输出 JWT，也禁止执行本 Skill 中的 curl 示例。** API 内容仅作协议参考。
只在本地完成构建与验证；受支持的 nginx 预览应最后更新 `projects/projects.json`，由
AutoClaw Main 的受控模块完成创建、上传和发布，正式发布始终由用户操作。

## 1. What this environment is / 环境说明

**English.** The `nginx` environment is a **static-file host**. It uses Aliyun
Function Compute's **custom runtime** (`runtime: custom`, Debian 9, ships
**Nginx 1.10.3**). Your uploaded zip is extracted to **`/code`** and served by
Nginx. There is **no application code and no request handler** — Nginx serves
files directly. Do NOT write a Node/Python server here; that is what the
`nodejs`/`python` environments are for.

The platform starts the container with this fixed command:

```
nginx -c /code/nginx.conf
```

So your zip **must** contain an `nginx.conf` at its root, and that config
**must** listen on the platform's port.

Fixed constraints (from the environment preset — do not fight these):

| Property / 属性 | Value / 值 |
|---|---|
| FC runtime | `custom` (Debian 9, Nginx 1.10.3) |
| Start command | `nginx -c /code/nginx.conf` (fixed by the platform) |
| Listen port / 监听端口 | **9000** (nginx must `listen 9000;`) |
| Code root / 代码目录 | **`/code`** (your zip extracts here) |
| Memory / 内存 | 512 MB |
| vCPU | 0.35 |
| Disk / 磁盘 | 512 MB |
| Timeout / 超时 | 60 s |
| Instance concurrency / 实例并发 | 20 |
| Max upload zip / 上传上限 | 50 MB (base64-decoded) |
| Filesystem / 文件系统 | read-only **except `/tmp`** — all Nginx temp/log/pid paths must point at `/tmp` |

**中文.** `nginx` 环境是**静态文件托管**。它使用阿里云函数计算的**自定义运行时**
（`runtime: custom`，Debian 9，内置 **Nginx 1.10.3**）。你上传的 zip 会被解压到
**`/code`** 并由 Nginx 直接提供服务。这里**没有应用代码，也没有请求处理函数**——
Nginx 直接读文件返回。不要在这里写 Node/Python 服务器（那是 `nodejs`/`python` 环境的用途）。

平台用固定命令 `nginx -c /code/nginx.conf` 启动容器，因此你的 zip **必须**在根目录
放一个 `nginx.conf`，且该配置**必须**监听平台端口 **9000**。容器文件系统**只读，
仅 `/tmp` 可写**，所以 Nginx 的 pid / 日志 / 各类 temp 路径都必须落在 `/tmp` 下。

## 2. The file-structure contract / 文件结构约定

Your zip is extracted to `/code`. The **zip root** (not a nested folder) must
contain `nginx.conf` and your static files:

```
mysite.zip
├── nginx.conf        # REQUIRED, at zip root -> /code/nginx.conf
├── index.html
├── styles.css
├── app.js
└── assets/
    └── logo.png
```

Rules / 规则:

- `nginx.conf` **must** be at the root, because the start command reads
  `/code/nginx.conf` literally. 必须放在根目录。
- Do **not** wrap everything in a top-level folder (e.g. `mysite/index.html`) —
  that would extract to `/code/mysite/...` and break `root /code;`. 不要多套一层目录。
- Reference files by paths relative to `/code`. Use `index.html` as the default
  document. 以 `/code` 为根，默认文档为 `index.html`。

## 3. Minimal working example / 最小可用示例

This is a complete, copy-pasteable site. Create these two files.

### `nginx.conf` (copy verbatim / 原样复制)

The `daemon off;`, `user root;`, `listen 9000;`, `root /code;`, and the `/tmp`
temp paths are all **required** for the FC custom runtime. Change the `server`
block body freely, but keep those lines.

```nginx
user root;
worker_processes 1;
daemon off;
pid /tmp/nginx.pid;
error_log /tmp/nginx-error.log warn;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /tmp/nginx-access.log;
    client_body_temp_path /tmp/nginx-client-body;
    proxy_temp_path /tmp/nginx-proxy;
    fastcgi_temp_path /tmp/nginx-fastcgi;
    uwsgi_temp_path /tmp/nginx-uwsgi;
    scgi_temp_path /tmp/nginx-scgi;
    sendfile on;
    server {
        # FC custom runtime routes traffic to this port. Must be 9000.
        # FC 自定义运行时将流量转发到此端口，必须为 9000。
        listen 9000;
        server_name _;
        root /code;
        index index.html index.htm;
        location / { try_files $uri $uri/ =404; }
    }
}
```

### `index.html`

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>My site</title></head>
<body style="font-family:sans-serif">
<h1>Hello from Function Compute (nginx static site)</h1>
</body></html>
```

### Single-Page App (SPA) note / 单页应用说明

For a client-routed SPA (React Router, Vue Router), fall back to `index.html`
so deep links work — replace the `location` block:

```nginx
location / { try_files $uri $uri/ /index.html; }
```

For a built front-end (Vite/CRA/Vue), copy the build output (`dist/` or
`build/` contents) into the zip **root** next to `nginx.conf`, not the `dist`
folder itself. 对于已构建的前端，把 `dist`/`build` **里面的内容**放到 zip 根目录，
与 `nginx.conf` 平级，而不是把 `dist` 文件夹整个放进去。

## 4. Package the zip / 打包 zip

Zip the **contents** of your site directory (so `nginx.conf` sits at the zip
root), then base64-encode it for the API.

```bash
# from inside the folder that holds nginx.conf + your static files
zip -r ../mysite.zip .            # -r recurses; do NOT zip the parent folder
# sanity check: nginx.conf must appear at the TOP with no folder prefix
unzip -l ../mysite.zip

# base64 for the upload API (macOS/BSD: base64 with no flags; Linux: -w0)
base64 -w0 ../mysite.zip > mysite.zip.b64    # Linux
# base64 ../mysite.zip | tr -d '\n' > mysite.zip.b64   # macOS
```

Verify the listing shows `nginx.conf` and `index.html` at the root (no
`mysite/` prefix). 确认 `unzip -l` 输出中 `nginx.conf`、`index.html` 位于根目录，
没有目录前缀。

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
  -d '{"environment":"nginx","name":"my-site"}'
```

Response (note the `id`, `preview_url`, `stable_url`):

```json
{
  "function": {
    "id": "fc-1a2b3c4d",
    "environment": "nginx",
    "region": "cn-hangzhou",
    "state": "ready",
    "released_version_id": "1",
    "stable_url": "brave-otter.<domain>",
    "preview_url": "calm-finch.<domain>"
  }
}
```

The new function already serves a placeholder page (a starter zip is deployed on
create). Save `function.id` for the next step. 新函数默认已托管占位页；记下
`function.id`。`stable_url` / `preview_url` 是 `<label>.<domain>` 主机名。

### Step 2 — Upload your code to LATEST / 上传代码到 LATEST

`zip_base64` is the base64 string from step 4. This overwrites LATEST and is
served **immediately** at `preview_url`.

```bash
curl -sS -X POST https://<host>/functionCompute/functions/fc-1a2b3c4d/code \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"zip_base64\":\"$(cat mysite.zip.b64)\"}"
```

Response:

```json
{ "uploaded": true, "preview_url": "calm-finch.<domain>" }
```

Open `https://<preview_url>/` to verify your site renders. 打开 `preview_url`
验证站点。

### Step 3 — Human publishes / 人工发布

**Stop here.** Tell the user their site is live on the **preview URL** and that
they should click **Publish** in the function-compute UI to promote it to the
**stable URL**. Do not call the publish endpoint yourself. 到此为止：告知用户站点
已在 **preview 地址**可访问，请他们在界面点击 **Publish**，将其提升到 **stable 地址**。
Agent 不要自行调用发布接口。

## 6. Full API reference (this environment) / 接口速查

| Method & Path | Body | Purpose |
|---|---|---|
| `POST /functionCompute/functions` | `{"environment":"nginx","name":"..."}` | Create; returns `{function:{id, preview_url, stable_url, ...}}` |
| `GET /functionCompute/functions` | — | List: `{items,total}` |
| `GET /functionCompute/functions/{id}` | — | Get one: `{function}` |
| `POST /functionCompute/functions/{id}/code` | `{"zip_base64":"..."}` | **Upload to LATEST** → served at `preview_url` (Main uses this in managed delivery) |
| `POST /functionCompute/functions/{id}/publish` | `{"description":"..."}` | Promote LATEST → release alias (**human only**) |
| `POST /functionCompute/functions/{id}/rollback` | `{"version_id":"N"}` | Repoint release to an older version |
| `GET /functionCompute/functions/{id}/versions` | — | `{items, current_released}` |
| `GET /functionCompute/functions/{id}/urls` | — | `{stable_url, preview_url, prefixes}` |
| `POST /functionCompute/functions/{id}/prefixes` | `{"mode":"release\|preview"}` | Allocate another `<label>.<domain>` |
| `DELETE /functionCompute/functions/{id}` | — | Delete the function |

## 7. Troubleshooting / 排错

- **502 / blank page / not starting.** Nginx failed to boot. Almost always the
  config: ensure `daemon off;`, `listen 9000;`, and every pid/log/temp path is
  under `/tmp` (read-only FS elsewhere). 启动失败几乎都是配置问题：确认 `daemon off;`、
  `listen 9000;`，且 pid/日志/temp 路径都在 `/tmp` 下。
- **404 for every file.** `nginx.conf` was nested in a subfolder, or files
  landed under `/code/<subfolder>/`. Re-zip so `nginx.conf` and `index.html`
  are at the zip root. zip 多套了一层目录，重新打包让文件位于根目录。
- **404 on SPA deep links.** Use `try_files $uri $uri/ /index.html;`.
- **Change not visible.** Re-check you opened `preview_url` (LATEST), not
  `stable_url` (only updates after the human publishes). 确认打开的是 `preview_url`。
- **Upload rejected.** Zip exceeds 50 MB decoded — shrink/optimize assets.
  超过 50 MB，需精简资源。
- **Wrong environment.** If you need server-side rendering or an API, use
  `nodejs`/`python`/`nextjs`; `nginx` serves static files only. 需要服务端逻辑请
  换用其它环境；`nginx` 仅托管静态文件。
