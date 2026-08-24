---
name: fc-nodejs-website
description: >-
  Build and deploy a Node.js website/app on the function-compute service (Aliyun
  FC 3.0 built-in nodejs20 runtime). Teaches the exact index.js handler contract,
  the real FC 3.0 HTTP request event shape (rawPath, requestContext.http.method,
  queryParameters, headers, body/isBase64Encoded), zip packaging, and the
  Main-process-managed create/upload protocol reference. Use this when the
  user asks to build, host, or deploy a Node.js (JavaScript) site, API, or web app
  on function-compute, or mentions the "nodejs" environment.
  在 function-compute 服务（阿里云 FC 3.0 内置 nodejs20 运行时）上构建并部署 Node.js
  网站/应用。讲解 index.js handler 约定、真实的 FC 3.0 HTTP 请求 event 结构（rawPath、
  requestContext.http.method、queryParameters、headers、body/isBase64Encoded）、zip
  打包方式，以及由 Main 进程受控执行的创建函数 / 上传代码流程参考。当用户需要在 function-compute
  上构建、托管或部署 Node.js（JavaScript）站点、接口或 Web 应用，或提到 "nodejs" 环境时使用本指南。
---

# Deploy a Node.js Website on Function Compute / 在函数计算上部署 Node.js 网站

## AutoClaw managed-delivery boundary (highest priority) / 受控交付边界（最高优先级）

When `website_delivery_start` or `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
is active, **do not call `/functionCompute`, read/request/store/output a JWT, or
execute this Skill's curl commands.** API sections are reference-only. Build,
package, and verify the artifact locally; AutoClaw Main owns create/upload, and
the human owns publication. The current managed automatic-preview path supports
nginx only, so do not add an nginx `autoPreview` marker for a Node.js package.

当 `website_delivery_start` 或 `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
生效时，**禁止调用 `/functionCompute`、读取/索取/保存/输出 JWT，禁止执行本 Skill 的 curl。**
API 章节仅作参考；Agent 只负责本地构建、打包与验证，创建和上传由 AutoClaw Main 负责，
正式发布由用户负责。当前自动预览仅支持 nginx，Node.js 产物不得写 nginx `autoPreview` 标记。

## TL;DR (English)

The `nodejs` environment is the Aliyun FC 3.0 **built-in `nodejs20` runtime**. You write a single `index.js` at the zip root that exports a `handler(event, context, callback)`. FC invokes that handler for every HTTP request and returns whatever you pass to `callback(null, {statusCode, headers, body})`.

Standalone API reference flow (not for AutoClaw-managed delivery):
1. `POST /functionCompute/functions` with `{"environment":"nodejs","name":"..."}` → get the function `id` + `stable_url` + `preview_url`.
2. Zip your `index.js` (at the root), base64-encode it, `POST /functionCompute/functions/{id}/code`. This goes to the **LATEST** version and is immediately live at `preview_url`.
3. **Stop there.** The Agent never publishes. The human clicks **Publish** in the UI to repoint `stable_url` to your new version.

## 一句话总结（中文）

`nodejs` 环境就是阿里云 FC 3.0 的**内置 `nodejs20` 运行时**。你在 zip 根目录写一个 `index.js`，导出 `handler(event, context, callback)`。FC 对每个 HTTP 请求调用该 handler，并返回你传给 `callback(null, {statusCode, headers, body})` 的内容。

独立 API 参考流程（AutoClaw 受控交付中不得执行）：
1. `POST /functionCompute/functions`，body 为 `{"environment":"nodejs","name":"..."}` → 得到函数 `id`、`stable_url`、`preview_url`。
2. 把 `index.js`（放在根目录）打成 zip，做 base64 编码，`POST /functionCompute/functions/{id}/code`。代码进入 **LATEST** 版本，立即在 `preview_url` 生效。
3. **到此为止。** Agent 永远不做发布（publish）。由人在 UI 点击 **Publish**，把 `stable_url` 切换到你的新版本。

---

## 1. Environment / 运行环境

**English**

| Property | Value |
|---|---|
| Runtime | `nodejs20` (FC built-in) — Node.js 20.x |
| Handler | `index.handler` (fixed — do not change) |
| Entry file | `index.js` at the **root** of the zip |
| CPU | 0.35 vCPU |
| Memory | 512 MB |
| Disk | 512 MB (writable `/tmp`) |
| Timeout | 60 s per request |
| Instance concurrency | 1 |
| Code location | Extracted to `/code`; `index.js` must be at `/code/index.js` |
| Port | N/A — built-in runtimes use the handler, not a listening port |
| Upload size | Base64 zip ≤ 50 MB decoded |

Constraints to respect: no port/`app.listen()` — the handler IS the server; requests are one-shot (no long-lived connections/WebSockets); each request must finish within 60 s; write only to `/tmp`; keep bundle small (no CDN at build time).

**中文**

| 属性 | 取值 |
|---|---|
| 运行时 | `nodejs20`（FC 内置）— Node.js 20.x |
| Handler | `index.handler`（固定，不要改） |
| 入口文件 | zip **根目录**下的 `index.js` |
| CPU | 0.35 vCPU |
| 内存 | 512 MB |
| 磁盘 | 512 MB（`/tmp` 可写） |
| 超时 | 每个请求 60 秒 |
| 实例并发 | 1 |
| 代码位置 | 解压到 `/code`；即 `/code/index.js` |
| 端口 | 无 — 内置运行时用 handler，而非监听端口 |
| 上传大小 | base64 解码后 zip ≤ 50 MB |

约束：不要监听端口或调用 `app.listen()` —— handler 就是服务器；请求是一次性的（不支持长连接 / WebSocket）；每个请求须在 60 秒内完成；只能写 `/tmp`；bundle 尽量小。

---

## 2. Handler contract / Handler 约定

**English** — `index.js` must export `handler` with exactly this signature. Call `callback(null, response)` on success or `callback(err)` on failure. When the function has an HTTP trigger, `event` arrives as **raw bytes** (a `Buffer`) of a JSON document — you MUST `JSON.parse(event.toString())` to read it.

**中文** —— `index.js` 必须导出严格如下签名的 `handler`。成功时调用 `callback(null, response)`，失败时 `callback(err)`。当函数带 HTTP 触发器时，`event` 是一段 JSON 文档的**原始字节**（`Buffer`），你必须用 `JSON.parse(event.toString())` 才能读取。

```js
exports.handler = (event, context, callback) => {
  // event is a Buffer of JSON when the function has an HTTP trigger.
  const req = JSON.parse(event.toString());
  // Correct field access (FC 3.0 HTTP-trigger event, version "v1"):
  //   req.requestContext.http.method  -> HTTP method (GET/POST/...)
  //   req.rawPath                      -> request path (also req.requestContext.http.path)
  //   req.queryParameters              -> query string map
  //   req.headers                      -> request headers map
  //   req.body                         -> request body (base64 when req.isBase64Encoded is true)
  callback(null, {
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    body: '<h1>Hello</h1>',
    // isBase64Encoded: true,  // set when body is base64 (e.g. images)
  });
};
```

### The event shape (verified) / event 结构（已验证）

**English** — The parsed `event` for an FC 3.0 HTTP trigger looks like this. Note there is **no** `httpMethod` and **no** `path` at the top level — use `requestContext.http.method` and `rawPath`.

**中文** —— FC 3.0 HTTP 触发器解析后的 `event` 如下。注意顶层**没有** `httpMethod`、**也没有** `path`——请改用 `requestContext.http.method` 和 `rawPath`。

```json
{
  "version": "v1",
  "rawPath": "/hello/world",
  "headers": { "Accept": "*/*", "User-Agent": "...", "X-Test-Header": "probe123" },
  "queryParameters": { "foo": "bar", "x": "1" },
  "body": "",
  "isBase64Encoded": true,
  "requestContext": {
    "accountId": "...", "domainName": "...", "domainPrefix": "...",
    "requestId": "...", "time": "...", "timeEpoch": "...",
    "http": { "method": "GET", "path": "/hello/world", "protocol": "HTTP/1.1", "sourceIp": "...", "userAgent": "..." }
  }
}
```

| What you want | Correct field | Do NOT use |
|---|---|---|
| HTTP method | `event.requestContext.http.method` | ~~`event.httpMethod`~~ (does not exist) |
| Request path | `event.rawPath` (or `event.requestContext.http.path`) | ~~`event.path`~~ (does not exist) |
| Query params | `event.queryParameters` | — |
| Headers | `event.headers` | — |
| Request body | `event.body` (base64 when `event.isBase64Encoded`) | — |

The response object shape (`statusCode`, `headers`, `body`) is required. `body` must be a string; for binary set `isBase64Encoded: true` and base64-encode `body`.

响应对象结构（`statusCode`、`headers`、`body`）是必需的。`body` 必须是字符串；返回二进制时设置 `isBase64Encoded: true` 并对 `body` 做 base64 编码。

---

## 3. Minimal working example / 最小可运行示例

This is the exact starter the environment ships. Put it in `index.js` at the zip root — nothing else is required.

这是本环境自带的原始示例。放到 zip 根目录的 `index.js` 即可，无需其他文件。

```js
// index.js
exports.handler = (event, context, callback) => {
  callback(null, {
    statusCode: 200,
    headers: { 'content-type': 'text/html' },
    body: '<html><body><h1>Hello from Function Compute (Node.js)</h1></body></html>',
  });
};
```

### A small router / 一个小型路由示例

```js
// index.js — routes by path + method, still a single handler
exports.handler = (event, context, callback) => {
  let req = {};
  try { req = JSON.parse(event.toString()); } catch (_) {}
  const path = req.rawPath || '/';
  const method = (req.requestContext && req.requestContext.http && req.requestContext.http.method) || 'GET';

  if (path === '/api/time' && method === 'GET') {
    return callback(null, {
      statusCode: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ now: new Date().toISOString() }),
    });
  }
  callback(null, {
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    body: '<html><body><h1>Home</h1><a href="/api/time">/api/time</a></body></html>',
  });
};
```

### Reading the request body / 读取请求体

The body is a string; when `isBase64Encoded` is `true` you must base64-decode it first.

body 是字符串；当 `isBase64Encoded` 为 `true` 时需先做 base64 解码。

```js
const raw = req.isBase64Encoded
  ? Buffer.from(req.body || '', 'base64').toString('utf8')
  : (req.body || '');
// e.g. const data = JSON.parse(raw);
```

### Using npm dependencies / 使用 npm 依赖

If you need packages, run `npm install` locally and include `node_modules/` inside the zip (there is no build step on FC). Keep the total decoded zip ≤ 50 MB.

如需第三方包，在本地执行 `npm install`，并把 `node_modules/` 一起打入 zip（FC 上没有构建步骤）。保证解码后 zip ≤ 50 MB。

```
myapp.zip
├── index.js          # required, at root / 必须在根目录
├── package.json      # optional
└── node_modules/     # optional, bundled deps / 打包的依赖
```

---

## 4. Package the zip / 打包 zip

**English** — Zip the **contents**, so `index.js` sits at the archive root (not inside a subfolder). Then base64-encode it.

**中文** —— 打包**文件内容**，使 `index.js` 位于压缩包根目录（而非子文件夹内）。然后做 base64 编码。

```bash
# from the directory that CONTAINS index.js
zip -r ../myapp.zip index.js            # add node_modules/ package.json if present
# verify index.js is at the root:
unzip -l ../myapp.zip                   # Name column should show "index.js", not "myapp/index.js"
# base64 for the API body:
base64 -w0 ../myapp.zip > myapp.b64     # macOS: base64 -i ../myapp.zip -o myapp.b64
```

---

## 5. Standalone API reference — prohibited in managed delivery / 独立 API 参考——受控交付中禁止执行

All endpoints are under `/functionCompute` and require `Authorization: Bearer <JWT>`.

所有接口都在 `/functionCompute` 下，需带 `Authorization: Bearer <JWT>`。

### Step 1 — Create the function / 创建函数

```bash
curl -X POST https://<host>/functionCompute/functions \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"environment":"nodejs","name":"my-node-site"}'
```

Response / 返回：

```json
{
  "function": {
    "id": "fc-1a2b3c4d",
    "environment": "nodejs",
    "region": "...",
    "state": "ready",
    "released_version_id": "1",
    "stable_url": "brave-otter.<domain>",
    "preview_url": "quiet-fox.<domain>"
  }
}
```

Save `function.id`. The function is created with the starter code already live, so `preview_url` works immediately.

保存 `function.id`。函数创建时已带示例代码，`preview_url` 立即可用。

### Step 2 — Upload your code (goes to LATEST → preview) / 上传代码（进入 LATEST → 预览）

```bash
ZIP_B64=$(base64 -w0 myapp.zip)
curl -X POST https://<host>/functionCompute/functions/fc-1a2b3c4d/code \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"zip_base64\":\"$ZIP_B64\"}"
```

Response / 返回：

```json
{ "uploaded": true, "preview_url": "quiet-fox.<domain>" }
```

The new code is now serving at `preview_url`. In managed delivery, Main owns
this operation and the Agent must not execute it.

新代码已在 `preview_url` 上提供服务。受控交付中该操作由 Main 执行，Agent 不得执行。

### Step 3 — Human publishes (Agent does NOT) / 由人发布（Agent 不做）

Tell the user: open the UI and click **Publish**. That calls `POST /functionCompute/functions/{id}/publish`, which repoints the release alias so `stable_url` serves the new version. Agents always upload to LATEST and never publish.

告知用户：在 UI 中点击 **Publish**。该操作调用 `POST /functionCompute/functions/{id}/publish`，把 release 别名指向新版本，使 `stable_url` 提供新版本。受控交付中创建和上传由 Main 执行，Agent 从不调用这些 API。

### Useful reads / 常用查询

```bash
# current URLs / 当前地址
curl -H "Authorization: Bearer $JWT" https://<host>/functionCompute/functions/fc-1a2b3c4d/urls
# → {"stable_url":"...","preview_url":"...","prefixes":[...]}

# versions + which one is released / 版本列表及当前发布版本
curl -H "Authorization: Bearer $JWT" https://<host>/functionCompute/functions/fc-1a2b3c4d/versions
# → {"items":[...],"current_released":"N"}
```

---

## 6. Checklist / 检查清单

- [ ] `index.js` is at the zip **root** and exports `handler` (English) / `index.js` 在 zip **根目录**并导出 `handler`（中文）
- [ ] `event` is parsed with `JSON.parse(event.toString())`; method read from `event.requestContext.http.method`, path from `event.rawPath` / 用 `JSON.parse(event.toString())` 解析 `event`；method 取 `event.requestContext.http.method`，path 取 `event.rawPath`
- [ ] Response returns `{statusCode, headers, body}` via `callback(null, ...)` / 通过 `callback(null, ...)` 返回 `{statusCode, headers, body}`
- [ ] No `app.listen()` / no port; work finishes within 60 s / 不监听端口，60 秒内完成
- [ ] `node_modules/` bundled if you used npm packages; decoded zip ≤ 50 MB / 用了 npm 依赖就打包 `node_modules/`，解码后 ≤ 50 MB
- [ ] Created with `environment: "nodejs"`, uploaded to LATEST, verified on `preview_url` / 用 `environment: "nodejs"` 创建、上传到 LATEST、在 `preview_url` 验证
- [ ] Left publishing to the human / 发布交给人工完成
