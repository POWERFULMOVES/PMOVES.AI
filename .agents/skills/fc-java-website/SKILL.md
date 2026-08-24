---
name: fc-java-website
description: >-
  Build and deploy a Java website/app on function-compute (Aliyun FC 3.0
  built-in java11 runtime, handler example.App::handleRequest). Use when an
  Agent creates an environment="java" function and uploads COMPILED bytecode (a
  class implementing com.aliyun.fc.runtime.StreamRequestHandler) — the runtime
  does NOT compile source (ship .class, not .java; source returns 502), and
  fc-java-core is provided at runtime. Covers the StreamRequestHandler contract,
  a verified example, compile+zip, and the create + upload-to-LATEST API (a
  human publishes).
  在 function-compute（阿里云 FC 3.0 内置 java11 运行时，处理函数
  example.App::handleRequest）上构建并部署 Java 网站/应用。当 Agent 用
  environment="java" 创建函数并上传【已编译】字节码（实现
  com.aliyun.fc.runtime.StreamRequestHandler 的类）时使用——运行时【不会】编译源码
  （上传 .class 而非 .java，源码会返回 502），fc-java-core 由运行时提供。涵盖
  StreamRequestHandler 契约、经验证示例、编译+打包，以及创建与上传到 LATEST 的 API
  （由人工发布）。
---

# Deploy a Java website on function-compute / 在 function-compute 上部署 Java 网站

## AutoClaw managed-delivery boundary (highest priority) / 受控交付边界（最高优先级）

When `website_delivery_start` or `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
is active, **do not call `/functionCompute`, read/request/store/output a JWT, or
execute this Skill's curl commands.** API sections are reference-only. Build,
package, and verify the artifact locally; AutoClaw Main owns create/upload, and
the human owns publication. The current managed automatic-preview path supports
nginx only, so do not add an nginx `autoPreview` marker for a Java package.

当 `website_delivery_start` 或 `AUTOCLAW_FUNCTION_COMPUTE_WEBSITE_PROTOCOL`
生效时，**禁止调用 `/functionCompute`、读取/索取/保存/输出 JWT，禁止执行本 Skill 的 curl。**
API 章节仅作参考；Agent 只负责本地构建、打包与验证，创建和上传由 AutoClaw Main 负责，
正式发布由用户负责。当前自动预览仅支持 nginx，Java 产物不得写 nginx `autoPreview` 标记。

## English

### 1. What the `java` environment is

The `java` environment runs on the **Aliyun FC 3.0 built-in `java11` runtime**. It is
**handler-based** (not a long-running server): FC invokes one method per HTTP request.

> **CRITICAL — this runtime does NOT compile source.** You MUST ship **compiled
> bytecode** (`.class` files). Shipping `App.java` as source returns **HTTP 502**. The
> deployable artifact is a zip of compiled classes, e.g. `example/App.class` at the zip
> root.

| Property | Value |
| --- | --- |
| Runtime | `java11` (built-in, Java 11) |
| Handler | `example.App::handleRequest` (fixed by the preset) |
| Memory | 512 MB |
| CPU | 0.35 vCPU |
| Disk | 512 MB |
| Timeout | 60 s per request |
| Instance concurrency | 1 |
| Code location | Extracted to `/code` inside the instance |
| Classpath | `/code` plus `/code/lib/*.jar` |
| Port | none — this is a handler runtime, do NOT open a socket |

Constraints to respect:
- **Ship compiled `.class`, never `.java`.** The built-in runtime executes your bytecode;
  it does not run a compiler. A source zip fails with HTTP 502.
- The handler string is **`example.App::handleRequest`**. Your compiled class must be
  `example.App`, implementing `com.aliyun.fc.runtime.StreamRequestHandler`. Do not rename
  it unless you also change the function's handler (the preset does not).
- One request per instance (concurrency 1); keep per-request work under the 60 s timeout.
- No inbound port and no custom start command — FC calls your method directly.

### 2. The handler contract

Your class **must implement `com.aliyun.fc.runtime.StreamRequestHandler`** and override:

```java
void handleRequest(InputStream input, OutputStream output, Context context)
```

- **`fc-java-core` is PROVIDED by the FC java11 runtime.** `com.aliyun.fc.runtime.Context`
  and `com.aliyun.fc.runtime.StreamRequestHandler` exist on the runtime classpath. **Do
  NOT bundle `fc-java-core`** in your zip — only compile against it (as a `provided`
  Maven dependency, or against a tiny stub of the two interfaces) and ship your own class.
- The request arrives as the **v1 event JSON** on the `InputStream`.
- You write the **v1 response JSON** — `{statusCode, headers, body, isBase64Encoded}` —
  as UTF-8 bytes to the `OutputStream`, then flush.

Response JSON fields:
- `statusCode` — integer HTTP status.
- `headers` — object of response headers (set `content-type`).
- `body` — the response body as a string (HTML/JSON/text). Escape it inside the JSON.
- `isBase64Encoded` — `true` if `body` is base64-encoded binary; `false` for text.

### 3. Verified working example (use verbatim)

This exact class is what the platform's built-in Java example ships as a compiled
`App.class`, and it is verified to return **HTTP 200**:

```java
package example;
import com.aliyun.fc.runtime.Context;
import com.aliyun.fc.runtime.StreamRequestHandler;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
public class App implements StreamRequestHandler {
    @Override
    public void handleRequest(InputStream input, OutputStream output, Context context) throws IOException {
        String html = "<html><body><h1>Hello from Function Compute (Java)</h1></body></html>";
        String body = html.replace("\\", "\\\\").replace("\"", "\\\"");
        String resp = "{\"statusCode\":200,\"headers\":{\"content-type\":\"text/html; charset=utf-8\"},\"body\":\"" + body + "\",\"isBase64Encoded\":false}";
        output.write(resp.getBytes(StandardCharsets.UTF_8));
        output.flush();
    }
}
```

### 4. File-structure contract

The uploaded `.zip` must contain **compiled classes** that satisfy the
`example.App::handleRequest` handler — `example.App` implementing
`StreamRequestHandler`. Put your compiled `example/App.class` at the **zip root** (it
extracts to `/code/example/App.class`). The classpath is rooted at `/code` plus
`/code/lib/*.jar`, so dependency jars go under `lib/`. **No `App.java`. No bundled
`fc-java-core`.**

```
your.zip
├── example/
│   └── App.class          # compiled example.App (implements StreamRequestHandler)
└── lib/                   # optional: your dependency jars on the classpath
    └── *.jar              # do NOT put fc-java-core here — it is provided by the runtime
```

The zip is valid as long as the compiled class `example.App` (with the
`handleRequest(InputStream, OutputStream, Context)` method) resolves on the runtime
classpath rooted at `/code`.

### 5. Build recipe

**Simplest (no Maven).** Compile against an `fc-java-core.jar` (or a stub of the two
interfaces), then zip the compiled classes so `example/App.class` sits at the zip root:

```bash
# src/example/App.java = the verified example from section 3
javac -cp fc-java-core.jar -d out src/example/App.java   # -> out/example/App.class
cd out && zip -r ../app.zip example && cd ..              # example/App.class at zip root
```

The zip root must contain the `example/` directory (not a wrapping folder). Verify with
`unzip -l app.zip` — you should see `example/App.class` and **no** `.java` and **no**
`fc-java-core` classes.

**Maven.** Declare `fc-java-core` as `provided` so it is compiled against but NOT packaged:

```xml
<dependency>
  <groupId>com.aliyun.fc.runtime</groupId>
  <artifactId>fc-java-core</artifactId>
  <version>1.4.1</version>
  <scope>provided</scope>
</dependency>
```

Then `mvn package` produces a jar of **your classes only** (fc-java-core excluded). Ship
it either by placing that jar under `lib/`, or by unzipping its classes to the zip root so
`example/App.class` is at the top level.

### 6. Standalone API reference — prohibited in managed delivery

1. **Create** the function with `environment="java"`.
2. **Upload** your compiled-class zip → it lands on the **LATEST** version and is
   immediately served at `preview_url`.
3. **The human clicks Publish in the UI** → repoints the release alias so `stable_url`
   serves your version. **Agents never publish.**

All calls are under `/functionCompute` and authenticated with
`Authorization: Bearer <JWT>`.

#### Create the function

```bash
curl -X POST https://<host>/functionCompute/functions \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"environment":"java","name":"my-java-site"}'
```

Response (note `id`, `preview_url`, `stable_url`):

```json
{"function":{"id":"fc-1a2b3c4d","environment":"java","region":"...",
  "state":"ready","released_version_id":"1",
  "stable_url":"<label>.<domain>","preview_url":"<label>.<domain>"}}
```

#### Upload the code zip (base64) → LATEST / preview

```bash
ZIP_B64=$(base64 -w0 app.zip)     # macOS: base64 -i app.zip | tr -d '\n'
curl -X POST https://<host>/functionCompute/functions/fc-1a2b3c4d/code \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"zip_base64\":\"$ZIP_B64\"}"
```

Response — open `preview_url` to see it live:

```json
{"uploaded":true,"preview_url":"<label>.<domain>"}
```

Zip limit: **50 MB** decoded. Then tell the user to open `preview_url`, and to click
**Publish** when satisfied. Under AutoClaw managed delivery, Main owns the
create/upload operations and the Agent must not execute them.

### 7. Handy endpoints

- `GET  /functionCompute/functions/{id}` → `{function}` (state, urls)
- `GET  /functionCompute/functions/{id}/urls` → `{stable_url, preview_url, prefixes}`
- `GET  /functionCompute/functions/{id}/versions` → `{items, current_released}`
- `POST /functionCompute/functions/{id}/publish` — human-only; repoints release alias
- `POST /functionCompute/functions/{id}/rollback` `{"version_id":"N"}`

---

## 中文

### 1. `java` 环境是什么

`java` 环境运行在**阿里云 FC 3.0 内置 `java11` 运行时**上，采用**处理函数模式**（不是常驻服务）：
FC 为每个 HTTP 请求调用一次方法。

> **关键 —— 该运行时【不会】编译源码。** 你必须上传**已编译的字节码**（`.class` 文件）。
> 以源码形式上传 `App.java` 会返回 **HTTP 502**。可部署产物是一个已编译 class 的 zip，
> 例如 `example/App.class` 位于 zip 根目录。

| 属性 | 取值 |
| --- | --- |
| 运行时 | `java11`（内置，Java 11） |
| 处理函数 | `example.App::handleRequest`（预设固定） |
| 内存 | 512 MB |
| CPU | 0.35 vCPU |
| 磁盘 | 512 MB |
| 超时 | 每请求 60 秒 |
| 实例并发 | 1 |
| 代码位置 | 解压到实例内的 `/code` |
| 类路径 | `/code` 以及 `/code/lib/*.jar` |
| 端口 | 无 —— 处理函数运行时，请勿监听端口 |

必须遵守的约束：
- **上传已编译的 `.class`，绝不上传 `.java`。** 内置运行时执行你的字节码，不会运行编译器。
  源码 zip 会以 HTTP 502 失败。
- 处理函数字符串为 **`example.App::handleRequest`**。你的已编译类必须是 `example.App`，
  并实现 `com.aliyun.fc.runtime.StreamRequestHandler`。不要改名（预设不会随之改动 handler）。
- 单实例单并发；每个请求的处理时间要控制在 60 秒超时以内。
- 没有入站端口、没有自定义启动命令 —— FC 直接调用你的方法。

### 2. 处理函数契约

你的类**必须实现 `com.aliyun.fc.runtime.StreamRequestHandler`** 并重写：

```java
void handleRequest(InputStream input, OutputStream output, Context context)
```

- **`fc-java-core` 由 FC java11 运行时提供。** `com.aliyun.fc.runtime.Context` 与
  `com.aliyun.fc.runtime.StreamRequestHandler` 已在运行时类路径上。**请勿把 `fc-java-core`
  打进 zip** —— 只在编译期依赖它（作为 Maven `provided` 依赖，或依赖这两个接口的极小 stub），
  只上传你自己的类。
- 请求以 **v1 事件 JSON** 到达 `InputStream`。
- 你把 **v1 响应 JSON** —— `{statusCode, headers, body, isBase64Encoded}` ——
  以 UTF-8 字节写入 `OutputStream`，然后 flush。

响应 JSON 字段：
- `statusCode` —— 整数 HTTP 状态码。
- `headers` —— 响应头对象（设置 `content-type`）。
- `body` —— 字符串形式的响应体（HTML/JSON/文本），需在 JSON 内转义。
- `isBase64Encoded` —— 若 `body` 为 base64 编码的二进制则为 `true`；文本为 `false`。

### 3. 经过验证的可用示例（请原样使用）

以下这个类正是平台内置 Java 示例所打包的已编译 `App.class`，并已验证返回 **HTTP 200**：

```java
package example;
import com.aliyun.fc.runtime.Context;
import com.aliyun.fc.runtime.StreamRequestHandler;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
public class App implements StreamRequestHandler {
    @Override
    public void handleRequest(InputStream input, OutputStream output, Context context) throws IOException {
        String html = "<html><body><h1>Hello from Function Compute (Java)</h1></body></html>";
        String body = html.replace("\\", "\\\\").replace("\"", "\\\"");
        String resp = "{\"statusCode\":200,\"headers\":{\"content-type\":\"text/html; charset=utf-8\"},\"body\":\"" + body + "\",\"isBase64Encoded\":false}";
        output.write(resp.getBytes(StandardCharsets.UTF_8));
        output.flush();
    }
}
```

### 4. 文件结构契约

上传的 `.zip` 必须包含满足 `example.App::handleRequest` 处理函数的**已编译 class** ——
即实现 `StreamRequestHandler` 的 `example.App`。把已编译的 `example/App.class` 放在
**zip 根目录**（它会解压到 `/code/example/App.class`）。类路径以 `/code` 为根，另加
`/code/lib/*.jar`，所以依赖 jar 放在 `lib/` 下。**不要有 `App.java`。不要打包
`fc-java-core`。**

```
your.zip
├── example/
│   └── App.class          # 编译后的 example.App（实现 StreamRequestHandler）
└── lib/                   # 可选：你的依赖 jar，在类路径上
    └── *.jar              # 请勿在此放 fc-java-core —— 它由运行时提供
```

只要以 `/code` 为根的运行时类路径能解析到含
`handleRequest(InputStream, OutputStream, Context)` 方法的已编译类 `example.App`，该 zip 即合法。

### 5. 构建方法

**最简单（无 Maven）。** 针对 `fc-java-core.jar`（或这两个接口的 stub）编译，然后把已编译
class 打包，使 `example/App.class` 位于 zip 根目录：

```bash
# src/example/App.java = 第 3 节中经过验证的示例
javac -cp fc-java-core.jar -d out src/example/App.java   # -> out/example/App.class
cd out && zip -r ../app.zip example && cd ..              # example/App.class 在 zip 根
```

zip 根目录必须直接包含 `example/` 目录（不要多套一层文件夹）。用 `unzip -l app.zip` 验证 ——
应看到 `example/App.class`，且**没有** `.java`、**没有** `fc-java-core` 的类。

**Maven。** 把 `fc-java-core` 声明为 `provided`，使其被编译依赖但**不被打包**：

```xml
<dependency>
  <groupId>com.aliyun.fc.runtime</groupId>
  <artifactId>fc-java-core</artifactId>
  <version>1.4.1</version>
  <scope>provided</scope>
</dependency>
```

随后 `mvn package` 产出**仅含你自己类**的 jar（不含 fc-java-core）。打包方式二选一：把该 jar
放到 `lib/` 下，或把它的类解压到 zip 根目录使 `example/App.class` 位于顶层。

### 6. 独立 API 参考——受控交付中禁止执行

1. **创建**函数，`environment="java"`。
2. **上传**已编译 class 的 zip → 落到 **LATEST** 版本，`preview_url` 立即提供访问。
3. **由人工在界面点击 Publish** → 重新指向 release 别名，使 `stable_url` 提供该版本。
   **Agent 从不发布。**

所有调用位于 `/functionCompute` 下，并用 `Authorization: Bearer <JWT>` 认证。

#### 创建函数

```bash
curl -X POST https://<host>/functionCompute/functions \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"environment":"java","name":"my-java-site"}'
```

响应（记下 `id`、`preview_url`、`stable_url`）：

```json
{"function":{"id":"fc-1a2b3c4d","environment":"java","region":"...",
  "state":"ready","released_version_id":"1",
  "stable_url":"<label>.<domain>","preview_url":"<label>.<domain>"}}
```

#### 上传代码 zip（base64）→ LATEST / preview

```bash
ZIP_B64=$(base64 -w0 app.zip)     # macOS：base64 -i app.zip | tr -d '\n'
curl -X POST https://<host>/functionCompute/functions/fc-1a2b3c4d/code \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"zip_base64\":\"$ZIP_B64\"}"
```

响应 —— 打开 `preview_url` 即可查看：

```json
{"uploaded":true,"preview_url":"<label>.<domain>"}
```

zip 上限：解码后 **50 MB**。随后请告知用户打开 `preview_url`，满意后点击 **Publish**
（这是人工步骤）。AutoClaw 受控交付中，创建和上传由 Main 执行，Agent 不得调用这些 API。

### 7. 常用端点

- `GET  /functionCompute/functions/{id}` → `{function}`（状态、URL）
- `GET  /functionCompute/functions/{id}/urls` → `{stable_url, preview_url, prefixes}`
- `GET  /functionCompute/functions/{id}/versions` → `{items, current_released}`
- `POST /functionCompute/functions/{id}/publish` —— 仅人工；重新指向 release 别名
- `POST /functionCompute/functions/{id}/rollback` `{"version_id":"N"}`
