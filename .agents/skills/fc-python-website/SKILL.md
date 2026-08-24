---
name: fc-python-website
description: >-
  Build and deploy a Python website or HTTP app on function-compute (Aliyun FC
  3.0, runtime python3.12). Covers the index.handler contract, index.py at the
  zip root, reading the raw-bytes HTTP event (json.loads, rawPath,
  requestContext.http.method), and the /functionCompute API to create an
  environment="python" function and upload code to LATEST (a human publishes).
  Use when an Agent must host or deploy Python code on function-compute.
  在 function-compute（阿里云 FC 3.0，运行时 python3.12）上构建并部署 Python 网站或
  HTTP 应用。涵盖 index.handler 约定、zip 根目录放 index.py、读取原始 bytes 请求事件
  （json.loads、rawPath、requestContext.http.method），以及创建 environment="python"
  函数并上传代码到 LATEST 的 /functionCompute API（由人工发布）。当 Agent 需要在
  function-compute 上托管或部署 Python 代码时使用。
---

# Deploy a Python App on Function-Compute / 在函数计算上部署 Python 应用

## AutoClaw managed-delivery boundary (highest priority) / 受控交付边界（最高优先级）

When `website_delivery_start` or `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
is active, **do not call `/functionCompute`, read/request/store/output a JWT, or
execute this Skill's curl commands.** API sections are reference-only. Build,
package, and verify the artifact locally; AutoClaw Main owns create/upload, and
the human owns publication. The current managed automatic-preview path supports
nginx only, so do not add an nginx `autoPreview` marker for a Python package.

当 `website_delivery_start` 或 `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
生效时，**禁止调用 `/functionCompute`、读取/索取/保存/输出 JWT，禁止执行本 Skill 的 curl。**
API 章节仅作参考；Agent 只负责本地构建、打包与验证，创建和上传由 AutoClaw Main 负责，
正式发布由用户负责。当前自动预览仅支持 nginx，Python 产物不得写 nginx `autoPreview` 标记。

## Standalone API reference (not managed delivery) / 独立 API 参考（不适用于受控交付）

1. Write `index.py` exporting `def handler(event, context)` that returns
   `{"statusCode", "headers", "body"}`.
2. Zip it with `index.py` **at the root** of the archive.
3. `POST /functionCompute/functions` with `{"environment":"python","name":"..."}` → get `id`.
4. `POST /functionCompute/functions/{id}/code` with `{"zip_base64":"<base64>"}` → your code is now live at **`preview_url`**.
5. Verify on `preview_url`. **You (the Agent) stop here.** The human clicks **Publish** in the UI to promote it to `stable_url`.

中文速览：

1. 编写 `index.py`，导出 `def handler(event, context)`，返回 `{"statusCode","headers","body"}`。
2. 打成 zip，`index.py` 必须在压缩包**根目录**。
3. `POST /functionCompute/functions`，body 为 `{"environment":"python","name":"..."}`，拿到 `id`。
4. `POST /functionCompute/functions/{id}/code`，body 为 `{"zip_base64":"<base64>"}`，代码即刻在 **`preview_url`** 可见。
5. 在 `preview_url` 自测。**Agent 到此为止**，由人工在 UI 点击 **Publish**，才会推送到 `stable_url`。

---

## 1. The Python environment / Python 运行环境

**English.** The `python` environment maps to the Aliyun Function Compute 3.0
**built-in runtime `python3.12`**. It uses FC's built-in HTTP handler: FC
receives the HTTP request, invokes your `handler`, and turns the returned dict
into the HTTP response. You do **not** open a socket or bind a port yourself —
that is only for custom runtimes (nginx / next.js). Your uploaded code is
extracted to **`/code`** inside the instance; `/code` is the working directory
and is on the import path.

Fixed resource preset (from the repo, do not assume you can change these):

| Property | Value |
|---|---|
| Runtime | `python3.12` |
| Handler | `index.handler` (file `index.py`, function `handler`) |
| CPU | 0.35 vCPU |
| Memory | 512 MB |
| Disk | 512 MB |
| Timeout | 60 s per request |
| Instance concurrency | 1 |
| Code location | extracted to `/code` |
| Max upload zip | 50 MB (base64 body) |

**中文。** `python` 环境对应阿里云函数计算 3.0 的**内置运行时 `python3.12`**，
使用 FC 内置 HTTP 处理器：FC 接收 HTTP 请求，调用你的 `handler`，并把返回的
字典转换成 HTTP 响应。你**不需要**自己监听端口或开 socket（那是 nginx /
next.js 等自定义运行时才做的）。上传的代码会解压到实例内的 **`/code`**，
`/code` 即工作目录，也在模块导入路径上。

资源规格是固定的（来自仓库预设，不要假设可以修改）：运行时 `python3.12`、
处理器 `index.handler`、CPU 0.35 核、内存 512 MB、磁盘 512 MB、单次请求
超时 60 秒、单实例并发 1、代码解压到 `/code`、上传 zip 上限 50 MB。

### Constraints to respect / 需要遵守的约束

- **Handler name is fixed.** It must be `index.handler` → file `index.py`, function `handler`. Do not rename.
- **Return a dict**, not a string. Keys: `statusCode` (int), `headers` (dict), `body` (str). Missing `statusCode` will error.
- **Requests over 60 s are killed.** Keep handlers fast; do not run long background loops.
- **512 MB memory / disk.** Vendor only the wheels you need. Large ML models will not fit.
- **Instance concurrency is 1** — one request per instance at a time; FC scales out with more instances.
- 处理器名称固定为 `index.handler`；必须返回字典（含 `statusCode`）；单次请求超过 60 秒会被终止；内存/磁盘各 512 MB；单实例并发为 1。

---

## 2. File-structure contract / 文件结构约定

The zip you upload must have `index.py` **at the top level** (not inside a
subfolder). Third-party packages must be vendored **beside** `index.py`
(install with `pip install -t .`), because there is no build step on upload.

```
mysite.zip
├── index.py          # REQUIRED, at root, defines handler(event, context)
├── requirements deps # optional: vendored packages next to index.py
│   └── ... (e.g. jinja2/, markupsafe/)
└── static/           # optional: your own assets you read from /code/static
```

上传的 zip 必须把 `index.py` 放在**最顶层**（不能在子目录里）。第三方依赖要
用 `pip install -t .` 装到 `index.py` **同级**目录，因为上传时没有构建步骤。

---

## 3. Minimal working example / 最小可运行示例

This is the exact starter that ships with the environment. Copy it verbatim as
`index.py` and it will serve HTML immediately.

```python
# index.py
def handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"content-type": "text/html"},
        "body": "<html><body><h1>Hello from Function Compute (Python)</h1></body></html>",
    }
```

### Reading the request / 读取请求

For the built-in HTTP handler, `event` arrives as **raw `bytes`** — a
JSON-encoded description of the HTTP request. You **must** `json.loads(event)`
to get a dict; there is no pre-parsed dict handed to you. The parsed object has
this shape (verified against real FC 3.0):

```json
{
  "version": "v1",
  "rawPath": "/hello/world",
  "headers": { "Accept": "*/*", "User-Agent": "...", "X-Test-Header": "probe123" },
  "queryParameters": { "foo": "bar", "x": "1" },
  "body": "",
  "isBase64Encoded": true,
  "requestContext": {
    "requestId": "...", "time": "...", "timeEpoch": "...",
    "http": { "method": "GET", "path": "/hello/world", "protocol": "HTTP/1.1", "sourceIp": "...", "userAgent": "..." }
  }
}
```

Field access (these are the correct names — there is **no** top-level
`httpMethod` and **no** top-level `path`):

| What you want | Where it is |
|---|---|
| HTTP method | `req["requestContext"]["http"]["method"]` |
| Request path | `req["rawPath"]` (also `req["requestContext"]["http"]["path"]`) |
| Query params | `req["queryParameters"]` (dict, may be absent) |
| Headers | `req["headers"]` (dict) |
| Request body | `req["body"]` + `req["isBase64Encoded"]` (body is base64 when the flag is true) |

Parse `event` and route on the real fields:

```python
import json

def handler(event, context):
    # event is raw bytes (JSON); always parse it to inspect the request
    req = json.loads(event)
    method = req["requestContext"]["http"]["method"]
    path = req.get("rawPath", "/")

    if path == "/health":
        return {"statusCode": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps({"ok": True})}

    return {
        "statusCode": 200,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": f"<h1>{method} {path}</h1>",
    }
```

Notes / 说明:
- Always set `content-type` in `headers`; browsers otherwise guess.
- Return a base64 body plus `"isBase64Encoded": true` for binary responses.
- `event` 以**原始 `bytes`** 传入（HTTP 请求的 JSON 编码），**必须**用
  `json.loads(event)` 解析成字典，不会有预解析好的字典。方法在
  `requestContext.http.method`，路径在 `rawPath`（等同
  `requestContext.http.path`）；查询参数 `queryParameters`、请求头 `headers`；
  请求体 `body`，当 `isBase64Encoded` 为 true 时 `body` 是 base64。**不存在**
  顶层 `httpMethod` 或顶层 `path` 字段。返回二进制时把 `body` 设为 base64 并加
  `"isBase64Encoded": true`。

---

## 4. Package the zip / 打包 zip

Zip from **inside** the code directory so `index.py` lands at the root, then
base64-encode the whole archive for the API body.

```bash
# from the folder that contains index.py
zip -r ../mysite.zip . -x '*.pyc' -x '__pycache__/*'

# base64 for the JSON request body (no newlines)
base64 -w0 ../mysite.zip > ../mysite.zip.b64   # macOS: base64 -i ../mysite.zip -o ../mysite.zip.b64
```

With vendored dependencies:

```bash
pip install -t . -r requirements.txt   # installs beside index.py
zip -r ../mysite.zip . -x '*.pyc' -x '__pycache__/*'
```

要点：务必在**包含 `index.py` 的目录内部**打包，让 `index.py` 位于 zip 根目录；
依赖用 `pip install -t .` 装到同级；再对整个 zip 做 base64（`-w0` 去掉换行）
作为 JSON 请求体。

Common mistake / 常见错误: zipping the parent folder so the archive contains
`mysite/index.py` — FC will not find the handler. 不要把父文件夹打进去导致出现
`mysite/index.py`，否则 FC 找不到处理器。

---

## 5. Standalone API reference — prohibited in managed delivery / 独立 API 参考——受控交付中禁止执行

All endpoints are under `/functionCompute` and require
`Authorization: Bearer <JWT>`. Set `$BASE` to the service host and `$JWT` to
your token.

所有接口都在 `/functionCompute` 下，需带 `Authorization: Bearer <JWT>`。

### Step 1 — Create the function / 创建函数

```bash
curl -sX POST "$BASE/functionCompute/functions" \
  -H "Authorization: Bearer $JWT" \
  -H "content-type: application/json" \
  -d '{"environment":"python","name":"my-python-site"}'
```

Response (grab `function.id` and `function.preview_url`):

```json
{"function":{
  "id":"fc-1a2b3c4d",
  "environment":"python",
  "region":"...",
  "state":"ready",
  "released_version_id":"1",
  "stable_url":"<label>.<domain>",
  "preview_url":"<label>.<domain>"
}}
```

`stable_url` and `preview_url` are `<label>.<domain>` hostnames. The new
function already serves the starter example until you upload your code.
`stable_url` / `preview_url` 是 `<label>.<domain>` 形式的主机名；在你上传代码前，
函数已经用自带示例对外服务。

### Step 2 — Upload your code to LATEST / 上传代码到 LATEST

```bash
ZIP_B64=$(cat mysite.zip.b64)
curl -sX POST "$BASE/functionCompute/functions/$FUNC_ID/code" \
  -H "Authorization: Bearer $JWT" \
  -H "content-type: application/json" \
  -d "{\"zip_base64\":\"$ZIP_B64\"}"
```

Response:

```json
{"uploaded":true,"preview_url":"<label>.<domain>"}
```

The upload goes to the **LATEST** version and is served **immediately at
`preview_url`**. Open `preview_url` in a browser to verify.
上传写入 **LATEST** 版本，并**立即在 `preview_url` 生效**；在浏览器打开
`preview_url` 自测。

### Step 3 — Human publishes (Agent does NOT) / 由人工发布（Agent 不发布）

The Agent's job ends after upload + verification. Report the `preview_url` to
the user and tell them to click **Publish** in the UI. Publishing repoints the
release alias so `stable_url` serves the new version.

Agent 的工作在“上传 + 自测”后结束。把 `preview_url` 交给用户，并告知其在 UI
点击 **Publish**；发布会把 release 别名指向新版本，`stable_url` 随之更新。

> Do not call `POST /functions/{id}/publish` from an Agent unless the human
> explicitly instructs it. Under AutoClaw managed delivery, Main owns upload to
> LATEST and the human owns publication; the Agent does not call these APIs.
> 除非人工明确要求，Agent 不要调用 `publish`。

---

## 6. API reference (Python-relevant) / API 速查

| Method & path | Body | Purpose |
|---|---|---|
| `POST /functionCompute/functions` | `{"environment":"python","name":"..."}` | Create; returns `function{id, preview_url, stable_url, ...}` |
| `GET /functionCompute/functions` | — | List (`{items,total}`) |
| `GET /functionCompute/functions/{id}` | — | Get one (`{function}`) |
| `POST /functionCompute/functions/{id}/code` | `{"zip_base64":"..."}` | Upload to LATEST → live on `preview_url` |
| `POST /functionCompute/functions/{id}/publish` | `{"description":"..."}` | **Human only** — promote LATEST to `stable_url` |
| `POST /functionCompute/functions/{id}/rollback` | `{"version_id":"N"}` | Repoint release alias to an old version |
| `GET /functionCompute/functions/{id}/versions` | — | `{items, current_released}` |
| `GET /functionCompute/functions/{id}/urls` | — | `{stable_url, preview_url, prefixes}` |
| `POST /functionCompute/functions/{id}/prefixes` | `{"mode":"release\|preview"}` | Allocate another `<label>.<domain>` |
| `DELETE /functionCompute/functions/{id}` | — | Delete the function |
| `GET /functionCompute/environments` | — | List environments |
| `GET /functionCompute/environments/python/guide` | — | This guide (raw markdown) |

Deploy model / 部署模型: **create (environment="python") → upload zip to
LATEST (visible at `preview_url`) → human clicks Publish (`stable_url`
serves it)**.

---

## 7. Troubleshooting / 排查

- **Blank page / handler not found** → `index.py` is inside a subfolder in the
  zip. Re-zip from inside the code dir. / `index.py` 被套进了子目录，重新打包。
- **500 / no `statusCode`** → the handler returned a string or a dict missing
  `statusCode`. Return `{"statusCode","headers","body"}`. / 必须返回含
  `statusCode` 的字典。
- **Routing sees the wrong method/path / `KeyError`** → you read `event`
  without parsing, or used `httpMethod`/`path`. `event` is raw bytes; call
  `json.loads(event)` and read `requestContext.http.method` and `rawPath`. /
  `event` 是原始 bytes，先 `json.loads(event)`，方法读 `requestContext.http.method`、
  路径读 `rawPath`，没有顶层 `httpMethod`/`path`。
- **`ModuleNotFoundError`** → dependency not vendored. Run `pip install -t .`
  beside `index.py` and re-zip. / 依赖未打包，用 `pip install -t .` 装到同级后重打包。
- **Timeout after 60 s** → the request ran too long; move slow work out of the
  request path. / 请求超过 60 秒被终止，缩短处理逻辑。
- **413 / upload rejected** → zip exceeds the 50 MB limit; trim vendored deps
  and assets. / zip 超过 50 MB，精简依赖与静态资源。
- **Change not on `stable_url`** → expected; only the human's Publish promotes
  LATEST from `preview_url` to `stable_url`. / 正常现象，只有人工 Publish 才会把
  LATEST 从 `preview_url` 推到 `stable_url`。
