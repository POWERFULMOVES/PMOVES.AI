# Submodule Test Matrix (Normalized)

- Generated: `2026-03-03 02:53 UTC`
- Total runs: **11**
- Results: **1 pass**, **9 fail**, **0 timeout**, **1 skip**

| Submodule | Command | Status | Exit | Duration(s) |
| --- | --- | --- | --- | --- |
| `PMOVES-Agent-Zero` | `uv run --no-project --with-requirements requirements.txt --with pytest python -m pytest -q tests --maxfail=1` | `fail` | `1` | `3.08` |
| `PMOVES-Archon` | `uv run --project python python -m pytest -q python/tests --maxfail=1` | `fail` | `4` | `1.49` |
| `PMOVES-BoTZ` | `uv run --no-project --with-requirements requirements.txt python scripts/smoke_tests.py` | `fail` | `1` | `40.91` |
| `PMOVES-BotZ-gateway` | `<no-test-harness-detected>` | `skip` | `` | `0` |
| `Pmoves-cipher` | `npm run test` | `fail` | `1` | `43.19` |
| `PMOVES-HiRAG` | `uv run --no-project --with-requirements requirements.txt --with pytest python -m pytest -q --maxfail=1` | `fail` | `1` | `10.35` |
| `PMOVES-transcribe-and-fetch` | `npm test -- --watch=false` | `fail` | `1` | `11.0` |
| `PMOVES-ToKenism-Multi` | `uv run --no-project --with-requirements requirements.txt --with pytest python -m pytest -q tests --maxfail=1` | `pass` | `0` | `21.79` |
| `PMOVES-DoX` | `uv run --project . python -m pytest -q tests --maxfail=1` | `fail` | `1` | `2.06` |
| `PMOVES-Open-Notebook` | `uv run --project . python -m pytest -q tests --maxfail=1` | `fail` | `1` | `55.96` |
| `PMOVES.YT` | `uv run --project . python -m pytest -Werror -q --maxfail=1` | `fail` | `1` | `2.78` |

## Tails

### PMOVES-Agent-Zero (fail)
```text
  × No solution found when resolving `--with` dependencies:
  ╰─▶ Because only the following versions of onnxruntime are available:
          onnxruntime<=1.17.0
          onnxruntime==1.17.1
          onnxruntime==1.17.3
          onnxruntime==1.18.0
          onnxruntime==1.18.1
          onnxruntime==1.19.0
          onnxruntime>=1.19.2
      and onnxruntime>=1.17.0,<=1.19.2 has no wheels with a
      matching Python ABI tag (e.g., `cp313`), we can conclude that
      onnxruntime>=1.17.0,<=1.19.2 cannot be used.
      And because langchain-unstructured==0.1.6 depends
      on onnxruntime>=1.17.0,<=1.19.2 and you require
      langchain-unstructured[all-docs]==0.1.6, we can conclude that your
      requirements are unsatisfiable.
      hint: You require CPython 3.13 (`cp313`), but we only found wheels for
      `onnxruntime` (v1.19.2) with the following Python ABI tags: `cp38`,
      `cp39`, `cp310`, `cp311`, `cp312`
```

### PMOVES-Archon (fail)
```text
warning: `VIRTUAL_ENV=C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves-cipher-mcp\.venv` does not match the project environment path `python\.venv` and will be ignored; use `--active` to target the active environment instead
ImportError while loading conftest 'C:\Users\russe\Documents\GitHub\PMOVES.AI\PMOVES-Archon\python\tests\conftest.py'.
python\tests\conftest.py:7: in <module>
    from fastapi.testclient import TestClient
E   ModuleNotFoundError: No module named 'fastapi'
```

### PMOVES-BoTZ (fail)
```text
[21:50:51] INFO: Starting PMOVES smoke tests...
[21:50:51] INFO: Running Environment Configuration tests...
[21:50:51] FAIL: No .env file found - copy from core/example.env
[21:50:51] FAIL: Environment Configuration tests FAILED
[21:50:51] INFO: Running Compose Stack Configuration tests...
[21:50:51] PASS: Docker Compose validation passed for stack botz_core_only
[21:50:52] PASS: Docker Compose validation passed for stack botz_core_metrics_external
[21:50:52] PASS: Docker Compose validation passed for stack botz_core_metrics_internal
[21:50:53] PASS: Docker Compose validation passed for stack botz_core_metrics_ephemeral
[21:50:53] PASS: Compose Stack Configuration tests PASSED
[21:50:53] INFO: Running Core Service Health tests...
[21:51:01] FAIL: Gateway Service: Health check error at http://localhost:2091/health: HTTPConnectionPool(host='localhost', port=2091): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=2091): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:01] FAIL: Docling Service: Health check error at http://localhost:3020/health: HTTPConnectionPool(host='localhost', port=3020): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3020): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:01] FAIL: Core Service Health tests FAILED
[21:51:01] INFO: Running VL-Sentinel Health tests...
[21:51:05] FAIL: VL-Sentinel: error reaching http://localhost:7072/health: HTTPConnectionPool(host='localhost', port=7072): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=7072): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:05] FAIL: VL-Sentinel Health tests FAILED
[21:51:05] INFO: Running Cipher Memory Integration tests...
[21:51:05] PASS: Cipher Cipher Submodule: Found at C:\Users\russe\Documents\GitHub\PMOVES.AI\PMOVES-BoTZ\features\cipher\pmoves_cipher
[21:51:05] FAIL: Cipher Cipher Build: Cipher not built - run setup script
[21:51:05] PASS: Cipher OpenAI API: No cloud LLM key set; cipher will run with limited capabilities until VENICE_API_KEY or OPENAI_API_KEY is provided
[21:51:05] PASS: Cipher Cipher Config: PMOVES cipher configuration found
[21:51:05] FAIL: Cipher Memory Integration tests FAILED
[21:51:05] INFO: Running Cipher Service Health tests...
[21:51:09] WARN: Cipher service API endpoint error at http://localhost:3011/health: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:13] WARN: Cipher service UI endpoint error at http://localhost:3010: HTTPConnectionPool(host='localhost', port=3010): Max retries exceeded with url: / (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3010): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:13] FAIL: Cipher service: no healthy API or UI endpoint detected
[21:51:13] FAIL: Cipher Service Health tests FAILED
[21:51:13] INFO: Running Cipher Functional API tests...
[21:51:17] FAIL: Cipher API health: error at http://localhost:3011/health: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:21] FAIL: Cipher agent discovery: error at http://localhost:3011/.well-known/agent.json: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /.well-known/agent.json (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:25] FAIL: Cipher sessions list: error at http://localhost:3011/api/sessions: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /api/sessions (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:25] FAIL: Cipher Functional API tests FAILED
[21:51:25] INFO: Running Cipher Message Roundtrip tests...
[21:51:25] PASS: Cipher message roundtrip: skipping (no real VENICE_API_KEY / OPENAI_API_KEY configured)
[21:51:25] PASS: Cipher Message Roundtrip tests PASSED
[21:51:25] INFO: Running YT Mini Agent tests...
[21:51:25] PASS: YT mini: skipping (PMOVES_YT_ENABLED != 1)
[21:51:25] PASS: YT Mini Agent tests PASSED
[21:51:25] INFO: Running Metrics Stack tests...
[21:51:25] PASS: Prometheus: reachable at http://localhost:9090/targets
[21:51:29] FAIL: Grafana: error reaching http://localhost:3033/login: HTTPConnectionPool(host='localhost', port=3033): Max retries exceeded with url: /login (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3033): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[21:51:29] FAIL: Metrics Stack tests FAILED
[21:51:29] INFO: Running API Connectivity tests...
[21:51:29] PASS: Postman API: Using test placeholder - skipping live test
[21:51:29] PASS: Tailscale: Tailscale auth key not required for basic functionality
[21:51:29] PASS: API Connectivity tests PASSED
[21:51:29] INFO: Smoke tests completed: 4/11 passed
[21:51:29] FAIL: 7 tests failed - Check configuration
Installed 18 packages in 239ms
```

### PMOVES-BotZ-gateway (skip)
```text
No root test harness detected.
```

### Pmoves-cipher (fail)
```text
[31m[1mSerialized Error:[22m[39m [90m{ errno: -4058, code: 'ENOENT', syscall: 'spawn /bin/bash', path: '/bin/bash', spawnargs: [] }[39m
[31mThis error originated in "[1msrc/core/brain/tools/definitions/system/__test__/bash.test.ts[22m" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.[39m
[31mThe latest test that might've caused the error is "[1mshould reuse existing active sessions[22m". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.[39m
[31m⎯⎯⎯⎯⎯[39m[1m[41m Uncaught Exception [49m[22m[31m⎯⎯⎯⎯⎯[39m
[31m[1mError[22m: spawn /bin/bash ENOENT[39m
[90m [2m❯[22m Process.ChildProcess._handle.onexit node:internal/child_process:[2m285:19[22m[39m
[90m [2m❯[22m onErrorNT node:internal/child_process:[2m483:16[22m[39m
[90m [2m❯[22m processTicksAndRejections node:internal/process/task_queues:[2m90:21[22m[39m
[31m[2m⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[22m[39m
[31m[1mSerialized Error:[22m[39m [90m{ errno: -4058, code: 'ENOENT', syscall: 'spawn /bin/bash', path: '/bin/bash', spawnargs: [] }[39m
[31mThis error originated in "[1msrc/core/brain/tools/definitions/system/__test__/bash.test.ts[22m" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.[39m
[31mThe latest test that might've caused the error is "[1mshould reuse existing active sessions[22m". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.[39m
[31m⎯⎯⎯⎯⎯[39m[1m[41m Uncaught Exception [49m[22m[31m⎯⎯⎯⎯⎯[39m
[31m[1mError[22m: spawn /bin/bash ENOENT[39m
[90m [2m❯[22m Process.ChildProcess._handle.onexit node:internal/child_process:[2m285:19[22m[39m
[90m [2m❯[22m onErrorNT node:internal/child_process:[2m483:16[22m[39m
[90m [2m❯[22m processTicksAndRejections node:internal/process/task_queues:[2m90:21[22m[39m
[31m[2m⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[22m[39m
[31m[1mSerialized Error:[22m[39m [90m{ errno: -4058, code: 'ENOENT', syscall: 'spawn /bin/bash', path: '/bin/bash', spawnargs: [] }[39m
[31mThis error originated in "[1msrc/core/brain/tools/definitions/system/__test__/bash.test.ts[22m" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.[39m
[31mThe latest test that might've caused the error is "[1mshould close specific sessions[22m". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.[39m
[31m⎯⎯⎯⎯⎯[39m[1m[41m Uncaught Exception [49m[22m[31m⎯⎯⎯⎯⎯[39m
[31m[1mError[22m: spawn /bin/bash ENOENT[39m
[90m [2m❯[22m Process.ChildProcess._handle.onexit node:internal/child_process:[2m285:19[22m[39m
[90m [2m❯[22m onErrorNT node:internal/child_process:[2m483:16[22m[39m
[90m [2m❯[22m processTicksAndRejections node:internal/process/task_queues:[2m90:21[22m[39m
[31m[2m⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[22m[39m
[31m[1mSerialized Error:[22m[39m [90m{ errno: -4058, code: 'ENOENT', syscall: 'spawn /bin/bash', path: '/bin/bash', spawnargs: [] }[39m
[31mThis error originated in "[1msrc/core/brain/tools/definitions/system/__test__/bash.test.ts[22m" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.[39m
[31mThe latest test that might've caused the error is "[1mshould close all sessions[22m". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.[39m
[31m⎯⎯⎯⎯⎯[39m[1m[41m Uncaught Exception [49m[22m[31m⎯⎯⎯⎯⎯[39m
[31m[1mError[22m: spawn /bin/bash ENOENT[39m
[90m [2m❯[22m Process.ChildProcess._handle.onexit node:internal/child_process:[2m285:19[22m[39m
[90m [2m❯[22m onErrorNT node:internal/child_process:[2m483:16[22m[39m
[90m [2m❯[22m processTicksAndRejections node:internal/process/task_queues:[2m90:21[22m[39m
[31m[2m⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[22m[39m
[31m[1mSerialized Error:[22m[39m [90m{ errno: -4058, code: 'ENOENT', syscall: 'spawn /bin/bash', path: '/bin/bash', spawnargs: [] }[39m
[31mThis error originated in "[1msrc/core/brain/tools/definitions/system/__test__/bash.test.ts[22m" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.[39m
[31mThe latest test that might've caused the error is "[1mshould close all sessions[22m". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.[39m
[31m⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[39m
```

### PMOVES-HiRAG (fail)
```text
      build\lib.win-amd64-cpython-313\tiktoken
      copying tiktoken\__init__.py -> build\lib.win-amd64-cpython-313\tiktoken
      creating build\lib.win-amd64-cpython-313\tiktoken_ext
      copying tiktoken_ext\openai_public.py ->
      build\lib.win-amd64-cpython-313\tiktoken_ext
      running egg_info
      writing tiktoken.egg-info\PKG-INFO
      writing dependency_links to tiktoken.egg-info\dependency_links.txt
      writing requirements to tiktoken.egg-info\requires.txt
      writing top-level names to tiktoken.egg-info\top_level.txt
      reading manifest file 'tiktoken.egg-info\SOURCES.txt'
      reading manifest template 'MANIFEST.in'
      adding license file 'LICENSE'
      writing manifest file 'tiktoken.egg-info\SOURCES.txt'
      copying tiktoken\py.typed -> build\lib.win-amd64-cpython-313\tiktoken
      running build_ext
      running build_rust
      [stderr]
      C:\Users\russe\AppData\Local\uv\cache\builds-v0\.tmpyuKjVL\Lib\site-packages\setuptools\config\_apply_pyprojecttoml.py:82:
      SetuptoolsDeprecationWarning: `project.license` as a TOML table is
      deprecated
      !!
      ********************************************************************************
              Please use a simple string containing a SPDX expression for
      `project.license`. You can also use `project.license-files`. (Both
      options available on setuptools>=77.0.0).
              By 2027-Feb-18, you need to update your project and remove
      deprecated calls
              or your builds will no longer be supported.
              See
      https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license
      for details.
      ********************************************************************************
      !!
        corresp(dist, value, root_dir)
      warning: no files found matching 'Makefile'
      error: can't find Rust compiler
      If you are using an outdated pip version, it is possible a prebuilt
      wheel is available for this package but pip is not able to install from
      it. Installing from the wheel would avoid the need for a Rust compiler.
      To update pip, run:
          pip install --upgrade pip
      and then retry package installation.
      If you did intend to build this package from source, try installing
      a Rust compiler from your system package manager and ensure it is
      on the PATH during installation. Alternatively, rustup (available at
      https://rustup.rs) is the recommended way to download and update the
      Rust compiler toolchain.
      hint: This usually indicates a problem with the package or the build
      environment.
```

### PMOVES-transcribe-and-fetch (fail)
```text
                            [36m<label[39m
                              [33mclass[39m=[32m"peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-sm font-normal"[39m
                              [33mfor[39m=[32m"docType-Full Transcript"[39m
                            [36m>[39m
                              [0mFull Transcript[0m
                            [36m</label>[39m
                          [36m</div>[39m
                          [36m<div[39m
                            [33mclass[39m=[32m"flex items-center space-x-2"[39m
                          [36m>[39m
                            [36m<button[39m
                              [33maria-checked[39m=[32m"false"[39m
                              [33mclass[39m=[32m"peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"[39m
                              [33mdata-state[39m=[32m"unchecked"[39m
                              [33mid[39m=[32m"docType-Document"[39m
                              [33mrole[39m=[32m"checkbox"[39m
                              [33mtype[39m=[32m"button"[39m
                              [33mvalue[39m=[32m"on"[39m
                            [36m/>[39m
                            [36m<label[39m
                              [33mclass[39m=[32m"peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-sm font-normal"[39m
                              [33mfor[39m=[32m"docType-Document"[39m
                            [36m>[39m
                              [0mDocument[0m
                            [36m</label>[39m
                          [36m</div>[39m
                          [36m<div[39m
                            [33mclass[39m=[32m"flex items-center space-x-2"[39m
                          [36m>[39m
                            [36m<button[39m
                              [33maria-checked[39m=[32m"false"[39m
                              [33mclass[39m=[32m"peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"[39m
                              [33mdata-state[39m=[32m"unchecked"[39m
                              [33mid[39m=[32m"docType-Webpage"[39m
                              [33mrole[39m=[32m"checkbox"[39m
                       ...
    [0m [90m 251 |[39m       })[33m;[39m
     [90m 252 |[39m
    [31m[1m>[22m[39m[90m 253 |[39m       [36mawait[39m waitFor(() [33m=>[39m {
     [90m     |[39m                    [31m[1m^[22m[39m
     [90m 254 |[39m         expect(screen[33m.[39mgetByText([35m/multi-tier architecture/[39m))[33m.[39mtoBeInTheDocument()[33m;[39m
     [90m 255 |[39m         expect(screen[33m.[39mgetByText([35m/System architecture/[39m))[33m.[39mtoBeInTheDocument()[33m;[39m
     [90m 256 |[39m       })[33m;[39m[0m
      at waitForWrapper (node_modules/@testing-library/dom/dist/wait-for.js:163:27)
      at Object.<anonymous> (src/app/vector-search/__tests__/page.test.js:253:20)
Test Suites: 10 failed, 2 passed, 12 total
Tests:       59 failed, 1 skipped, 23 passed, 83 total
Snapshots:   0 total
Time:        9.64 s
Ran all test suites.
```

### PMOVES-ToKenism-Multi (pass)
```text
..........................................                               [100%]
42 passed in 12.72s
   Building proxy-tools==0.1.0
Downloading pyinstaller (1.3MiB)
 Downloading pyinstaller
      Built proxy-tools==0.1.0
Installed 40 packages in 2.74s
```

### PMOVES-DoX (fail)
```text
warning: `VIRTUAL_ENV=C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves-cipher-mcp\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Using CPython 3.13.5
Creating virtual environment at: .venv
   Building pmoves-dox-tools @ file:///C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES-DoX
  × Failed to build `pmoves-dox-tools @
  │ file:///C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES-DoX`
  ├─▶ The build backend returned an error
  ╰─▶ Call to `setuptools.build_meta.build_editable` failed (exit code: 1)
      [stderr]
      error: Multiple top-level packages discovered in a flat-layout:
      ['chit', 'nginx', 'smoke', 'config', 'backend', 'samples', 'external',
      'frontend', 'pmoves_health', 'A2UI_reference', 'pmoves_registry',
      'pmoves_announcer', 'PsyFeR_reference'].
      To avoid accidental inclusion of unwanted files or directories,
      setuptools will not proceed with this build.
      If you are trying to create a single distribution with multiple packages
      on purpose, you should not rely on automatic discovery.
      Instead, consider the following options:
      1. set up custom discovery (`find` directive with `include` or
      `exclude`)
      2. use a `src-layout`
      3. explicitly set `py_modules` or `packages` with a list of names
      To find more information, look for "package discovery" on setuptools
      docs.
      hint: This usually indicates a problem with the package or the build
      environment.
```

### PMOVES-Open-Notebook (fail)
```text
.venv\Lib\site-packages\surreal_commands\core\retry.py:41
  C:\Users\russe\Documents\GitHub\PMOVES.AI\PMOVES-Open-Notebook\.venv\Lib\site-packages\surreal_commands\core\retry.py:41: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class RetryConfig(BaseModel):
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_models_api.py::TestModelCreation::test_create_duplicate_model_same_case
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 65 passed, 1 warning in 25.06s
warning: `VIRTUAL_ENV=C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves-cipher-mcp\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Using CPython 3.12.9
Creating virtual environment at: .venv
   Building open-notebook @ file:///C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES-Open-Notebook
Downloading pymupdf (17.6MiB)
Downloading imageio-ffmpeg (29.8MiB)
Downloading lupa (1.6MiB)
Downloading sqlalchemy (2.0MiB)
Downloading pywin32 (9.1MiB)
Downloading pillow (6.7MiB)
Downloading google-cloud-aiplatform (7.8MiB)
Downloading lxml (3.8MiB)
Downloading pip (1.7MiB)
Downloading pandas (9.3MiB)
Downloading pyarrow (26.7MiB)
Downloading hf-xet (2.8MiB)
Downloading surrealdb (4.8MiB)
Downloading pytubefix (1.4MiB)
Downloading nodejs-wheel-binaries (39.4MiB)
Downloading langchain-community (2.4MiB)
Downloading beartype (1.3MiB)
 Downloading pytubefix
      Built open-notebook @ file:///C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES-Open-Notebook
 Downloading lupa
   Building langdetect==1.0.9
 Downloading sqlalchemy
 Downloading pip
 Downloading beartype
 Downloading hf-xet
 Downloading lxml
 Downloading surrealdb
 Downloading langchain-community
 Downloading pillow
 Downloading pandas
 Downloading google-cloud-aiplatform
 Downloading pymupdf
 Downloading imageio-ffmpeg
 Downloading pywin32
      Built langdetect==1.0.9
 Downloading pyarrow
 Downloading nodejs-wheel-binaries
Installed 232 packages in 8.56s
```

### PMOVES.YT (fail)
```text
warning: `VIRTUAL_ENV=C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves-cipher-mcp\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Using CPython 3.13.5
Creating virtual environment at: .venv
   Building yt-dlp @ file:///C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES.YT
      Built yt-dlp @ file:///C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES.YT
Installed 1 package in 18ms
C:\Users\russe\Documents\GitHub\PMOVES.AI\PMOVES.YT\.venv\Scripts\python.exe: No module named pytest
```