---
name: fc-nginx-website
description: >-
  Hosting-environment rules for AutoClaw's managed static website preview on the
  function-compute "nginx" environment: what the environment can and cannot
  serve, how the entry file decides which files get uploaded, and the size
  limits. Use this whenever a request becomes a hosted website, landing page,
  docs site, or built front-end (React/Vue/Vite dist, Hugo/Jekyll output).
  AutoClaw 受控静态网站预览的托管环境规则（function-compute 的 nginx 环境）：
  能托管什么、入口文件如何决定上传范围、体积上限。凡是要交付可访问网站、落地页、
  文档站或已构建前端产物时使用。
---

# Managed static website hosting on function-compute (nginx)
# 受控静态网站托管（function-compute nginx 环境）

## Managed delivery — the only mode / 受控交付（唯一模式）

This is an AutoClaw-managed delivery. You author files; AutoClaw Main packages
and uploads them. **Do not call any `/functionCompute` API, and do not read,
request, store, or output a JWT.** Creating the function, uploading to LATEST,
and formal publication are not yours to perform — the preview upload is Main's
job, and formal publication belongs to the user clicking Publish.

Do not write `nginx.conf` (a model-authored one is discarded), do not build a
zip, and do not base64-encode anything. Do not guess or assemble a preview
domain: AutoClaw appends the real URL to the conversation when the deployment
reaches a terminal state.

Division of labour: `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL` owns the flow —
project identity from `website_delivery_start`, where files go, and the
`projects/projects.json` write that triggers deployment. This Skill owns the
hosting environment: what nginx can serve, how the entry file decides the upload
scope, and the size limits.

本任务属于 AutoClaw 受控交付：你只负责产出文件，打包与上传由 AutoClaw Main 完成。
**禁止调用任何 `/functionCompute` API，禁止读取、索取、保存或输出 JWT。** 创建函数、
上传 LATEST、正式发布都不由你执行；正式域名只在用户点击「发布」后启用。
不要自己写 `nginx.conf`（写了也会被丢弃），不要打包 zip，不要做 base64 编码，
也不要猜测或拼接预览域名——部署到达终态后系统会把真实 URL 追加到会话里。

分工：流程由 `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL` 规定（项目身份来自
`website_delivery_start`、产物落点、以及触发部署的 `projects/projects.json` 写入）；
本 Skill 规定托管环境（nginx 能托管什么、入口文件如何决定上传范围、体积上限）。

## What this environment can serve / 环境能力

The `nginx` environment is a **static-file host**: Nginx reads files off disk and
returns them. There is no application process, no request handler, and no build
step on the server.

- Works: HTML/CSS/JS, images, fonts, and any pre-built front-end output
  (Vite/CRA/Vue `dist`, Hugo/Jekyll output).
- Does not work: SSR, API routes, databases, WebSocket servers, cron, or
  anything that needs a long-running process. Build to static output instead, or
  state plainly that this channel cannot host it — never fake a preview.
- Client-side routing works: the managed config already falls back to
  `index.html`, so React Router / Vue Router deep links resolve.

`nginx` 环境是**纯静态文件托管**：没有应用进程、没有请求处理函数、服务端不会构建。
SSR、API、数据库、常驻进程都无法托管——请改为构建成静态产物，或直接如实说明限制。
客户端路由无需额外配置：受控 nginx 配置已经回退到 `index.html`，深链可用。

## The entry file decides what gets uploaded / 入口文件决定上传范围

**The site root is the directory containing `entryFile`, and only that subtree is
uploaded.** This is the single most common way to silently lose files.

- `entryFile: "index.html"` → site root is the project directory; everything
  under it ships.
- `entryFile: "dist/index.html"` → site root is `dist/`; **nothing outside
  `dist/` is uploaded**, so a stylesheet or image left at the project root will
  404 in preview.

Rules / 规则:

- `entryFile` must be a relative path inside the project directory pointing at an
  existing file. Absolute paths and `..` segments are rejected.
- A `dist/index.html` / `build/index.html` fallback exists **only** when
  `entryFile` is exactly `index.html` or `index.htm`. Any other name has no
  fallback — it must exist exactly where you said.
- If the entry file is not named `index.html`, it is also copied to
  `index.html` so `/` serves it.
- Keep the site root clean: the only exclusions are `.DS_Store`, `.git`,
  `.svn`, `node_modules`, the deployments bookkeeping file, `.env*`, and
  symlinks. `.ts`, `.vue`, `.map`, and stray source files **do** ship. Nothing
  secret belongs anywhere under the site root.

**站点根目录 = `entryFile` 所在目录，且只有这一棵子树会被上传。** 这是最容易静默丢文件
的一点：`entryFile: "dist/index.html"` 时，项目根下的文件一个都不会上传。
`entryFile` 必须是项目目录内、指向真实文件的相对路径，不能是绝对路径，也不能含 `..`；
只有 `entryFile` 恰好是 `index.html` / `index.htm` 时才会回退查找
`dist/index.html`、`build/index.html`。入口不叫 `index.html` 时会被复制一份为
`index.html`。排除清单只有 `.DS_Store` / `.git` / `.svn` / `node_modules` /
部署记账文件 / `.env*` / 符号链接——`.ts`、`.vue`、sourcemap 都会照传，站点根目录里
不要留源码和任何机密文件。

## Size limits / 体积上限

| Limit / 上限 | Value / 值 |
|---|---|
| Source files under the site root / 站点根文件数 | 5000 |
| Total source size / 源文件总大小 | 100 MB |
| Upload body after base64 / base64 编码后的上传体积 | 50 MB |

Optimize images and drop unused build artifacts before they become the reason a
deployment is rejected. 提前压缩图片、清掉无用产物，避免因体积被拒。

## Troubleshooting the preview / 预览期排错

- **Blank page or 404 on assets.** Almost always the site root: the entry file's
  directory did not contain the referenced files, or the page uses absolute
  paths that do not exist in the uploaded subtree. Use relative asset paths and
  keep everything under the site root. 白屏或资源 404：基本都是站点根目录问题。
- **404 on a specific page.** Client-side routing already falls back to
  `index.html`; a real 404 means the file is not in the uploaded subtree.
- **Changes not visible.** The preview URL serves the latest upload; the stable
  URL only changes after the user publishes. 改动看不到：确认打开的是预览地址。
- **Upload rejected for size.** See the limits above — shrink assets.
