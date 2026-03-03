# Submodule Test Matrix (Curated)

- Generated: `2026-03-03 03:19 UTC`
- Results: **4 pass**, **5 fail**, **0 timeout**, **2 skip**

| Submodule | Status | Exit | Duration(s) | Command |
| --- | --- | --- | --- | --- |
| `PMOVES-Agent-Zero` | `fail` | `1` | `0.15` | `uv run --python 3.11 --no-project --with-requirements requirements.txt --with-requirements requirements2.txt --with pytest python -m pytest -q tests --maxfail=1` |
| `PMOVES-Archon` | `pass` | `0` | `97.15` | `uv run --python 3.12 --project python --group all python -m pytest -q python/tests --maxfail=1` |
| `PMOVES-BoTZ` | `fail` | `1` | `38.91` | `uv run --python 3.11 --no-project --with-requirements requirements.txt --with python-dotenv python scripts/smoke_tests.py` |
| `PMOVES-BotZ-gateway` | `skip` | `` | `0` | `<no-root-test-harness>` |
| `Pmoves-cipher` | `pass` | `0` | `42.83` | `npm run test` |
| `PMOVES-HiRAG` | `skip` | `` | `0` | `<no-root-test-harness>` |
| `PMOVES-transcribe-and-fetch` | `fail` | `1` | `10.82` | `npm test -- --watch=false` |
| `PMOVES-ToKenism-Multi` | `pass` | `0` | `3.19` | `uv run --python 3.11 --no-project --with-requirements requirements.txt --with pytest python -m pytest -q tests --maxfail=1` |
| `PMOVES-DoX` | `fail` | `1` | `17.8` | `set SUPABASE_JWT_SECRET=test-secret&& uv run --python 3.12 --no-project --with-requirements backend/requirements.txt --with pytest --with pytest-asyncio python -m pytest -q backend/tests --maxfail=1` |
| `PMOVES-Open-Notebook` | `pass` | `0` | `17.99` | `uv run --project . python -m pytest -q tests --maxfail=1` |
| `PMOVES.YT` | `fail` | `1` | `13.27` | `uv run --python 3.11 --with pytest python -m pytest -q --maxfail=1` |

## Output Tails

### PMOVES-Agent-Zero (fail)
```text
  × No solution found when resolving `--with` dependencies:
  ╰─▶ Because browser-use==0.5.11 depends on openai==1.99.2 and you require
      browser-use==0.5.11, we can conclude that you require openai==1.99.2.
      And because you require openai==1.99.5, we can conclude that your
      requirements are unsatisfiable.
```

### PMOVES-Archon (pass)
```text
python\tests\mcp_server\features\documents\test_version_tools.py ....    [ 27%]
python\tests\mcp_server\features\projects\test_project_tools.py ....     [ 28%]
python\tests\mcp_server\features\tasks\test_task_tools.py ......         [ 29%]
python\tests\mcp_server\features\test_feature_tools.py ...               [ 29%]
python\tests\mcp_server\utils\test_error_handling.py ..........          [ 30%]
python\tests\mcp_server\utils\test_timeout_config.py .............       [ 32%]
python\tests\progress_tracking\integration\test_crawl_orchestration_progress.py . [ 32%]
....                                                                     [ 33%]
python\tests\progress_tracking\integration\test_document_storage_progress.py . [ 33%]
......                                                                   [ 34%]
python\tests\progress_tracking\test_batch_progress_bug.py ...            [ 34%]
python\tests\progress_tracking\test_progress_api.py .........            [ 35%]
python\tests\progress_tracking\test_progress_mapper.py ................. [ 38%]
                                                                         [ 38%]
python\tests\progress_tracking\test_progress_models.py ................. [ 40%]
....                                                                     [ 40%]
python\tests\progress_tracking\test_progress_tracker.py .............    [ 42%]
python\tests\server\api_routes\test_bug_report_api.py .......            [ 43%]
python\tests\server\api_routes\test_mcp_api.py ..............            [ 45%]
python\tests\server\api_routes\test_migration_api.py .........           [ 46%]
python\tests\server\api_routes\test_projects_api_polling.py .........    [ 48%]
python\tests\server\api_routes\test_version_api.py .......               [ 48%]
python\tests\server\services\test_llms_full_parser.py ...........        [ 50%]
python\tests\server\services\test_migration_service.py ...........       [ 51%]
python\tests\server\services\test_version_service.py ............        [ 53%]
python\tests\server\utils\test_etag_utils.py ..............              [ 55%]
python\tests\test_api_essentials.py ..........                           [ 56%]
python\tests\test_async_credential_service.py ...............            [ 58%]
python\tests\test_async_embedding_service.py ..........                  [ 60%]
python\tests\test_async_llm_provider_service.py .....................    [ 63%]
python\tests\test_async_source_summary.py .......                        [ 64%]
python\tests\test_business_logic.py ..........                           [ 65%]
python\tests\test_code_extraction_source_id.py ....                      [ 65%]
python\tests\test_crawl_orchestration_isolated.py ..................     [ 68%]
python\tests\test_crawling_service_subdomain.py ........                 [ 69%]
python\tests\test_discovery_service.py ...........                       [ 70%]
python\tests\test_document_storage_metrics.py ....                       [ 71%]
python\tests\test_embedding_service_no_zeros.py ............             [ 73%]
python\tests\test_keyword_extraction.py .................                [ 75%]
python\tests\test_knowledge_api_integration.py ssss.s                    [ 76%]
python\tests\test_knowledge_api_pagination.py .ssss..s                   [ 77%]
python\tests\test_llms_txt_link_following.py .......                     [ 78%]
python\tests\test_openrouter_discovery.py ...........                    [ 79%]
python\tests\test_port_configuration.py ............                     [ 81%]
python\tests\test_progress_api.py ...........                            [ 82%]
python\tests\test_rag_simple.py ..................                       [ 85%]
python\tests\test_rag_strategies.py ....................                 [ 88%]
python\tests\test_service_integration.py ..........                      [ 89%]
python\tests\test_settings_api.py ...                                    [ 89%]
python\tests\test_source_id_refactor.py .................                [ 92%]
python\tests\test_source_race_condition.py .....                         [ 92%]
python\tests\test_source_url_shadowing.py ..                             [ 93%]
python\tests\test_supabase_validation.py ...........                     [ 94%]
python\tests\test_task_counts.py ...                                     [ 94%]
python\tests\test_token_optimization.py ........                         [ 96%]
python\tests\test_token_optimization_integration.py ss..                 [ 96%]
python\tests\test_url_canonicalization.py ..........                     [ 97%]
python\tests\test_url_handler.py ...............                         [100%]
=========== 725 passed, 12 skipped, 64 warnings in 92.53s (0:01:32) ===========
warning: `VIRTUAL_ENV=<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv` does not match the project environment path `python\.venv` and will be ignored; use `--active` to target the active environment instead
```

### PMOVES-BoTZ (fail)
```text
[22:17:19] INFO: Starting PMOVES smoke tests...
[22:17:19] INFO: Running Environment Configuration tests...
[22:17:19] FAIL: No .env file found - copy from core/example.env
[22:17:19] FAIL: Environment Configuration tests FAILED
[22:17:19] INFO: Running Compose Stack Configuration tests...
[22:17:19] PASS: Docker Compose validation passed for stack botz_core_only
[22:17:20] PASS: Docker Compose validation passed for stack botz_core_metrics_external
[22:17:20] PASS: Docker Compose validation passed for stack botz_core_metrics_internal
[22:17:21] PASS: Docker Compose validation passed for stack botz_core_metrics_ephemeral
[22:17:21] PASS: Compose Stack Configuration tests PASSED
[22:17:21] INFO: Running Core Service Health tests...
[22:17:29] FAIL: Gateway Service: Health check error at http://localhost:2091/health: HTTPConnectionPool(host='localhost', port=2091): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=2091): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:29] FAIL: Docling Service: Health check error at http://localhost:3020/health: HTTPConnectionPool(host='localhost', port=3020): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3020): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:29] FAIL: Core Service Health tests FAILED
[22:17:29] INFO: Running VL-Sentinel Health tests...
[22:17:33] FAIL: VL-Sentinel: error reaching http://localhost:7072/health: HTTPConnectionPool(host='localhost', port=7072): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=7072): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:33] FAIL: VL-Sentinel Health tests FAILED
[22:17:33] INFO: Running Cipher Memory Integration tests...
[22:17:33] PASS: Cipher Cipher Submodule: Found at <WORKSTATION_PATH>\PMOVES-BoTZ\features\cipher\pmoves_cipher
[22:17:33] FAIL: Cipher Cipher Build: Cipher not built - run setup script
[22:17:33] PASS: Cipher OpenAI API: No cloud LLM key set; cipher will run with limited capabilities until VENICE_API_KEY or OPENAI_API_KEY is provided
[22:17:33] PASS: Cipher Cipher Config: PMOVES cipher configuration found
[22:17:33] FAIL: Cipher Memory Integration tests FAILED
[22:17:33] INFO: Running Cipher Service Health tests...
[22:17:37] WARN: Cipher service API endpoint error at http://localhost:3011/health: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:41] WARN: Cipher service UI endpoint error at http://localhost:3010: HTTPConnectionPool(host='localhost', port=3010): Max retries exceeded with url: / (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3010): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:41] FAIL: Cipher service: no healthy API or UI endpoint detected
[22:17:41] FAIL: Cipher Service Health tests FAILED
[22:17:41] INFO: Running Cipher Functional API tests...
[22:17:45] FAIL: Cipher API health: error at http://localhost:3011/health: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:49] FAIL: Cipher agent discovery: error at http://localhost:3011/.well-known/agent.json: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /.well-known/agent.json (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:53] FAIL: Cipher sessions list: error at http://localhost:3011/api/sessions: HTTPConnectionPool(host='localhost', port=3011): Max retries exceeded with url: /api/sessions (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3011): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:53] FAIL: Cipher Functional API tests FAILED
[22:17:53] INFO: Running Cipher Message Roundtrip tests...
[22:17:53] PASS: Cipher message roundtrip: skipping (no real VENICE_API_KEY / OPENAI_API_KEY configured)
[22:17:53] PASS: Cipher Message Roundtrip tests PASSED
[22:17:53] INFO: Running YT Mini Agent tests...
[22:17:53] PASS: YT mini: skipping (PMOVES_YT_ENABLED != 1)
[22:17:53] PASS: YT Mini Agent tests PASSED
[22:17:53] INFO: Running Metrics Stack tests...
[22:17:53] PASS: Prometheus: reachable at http://localhost:9090/targets
[22:17:57] FAIL: Grafana: error reaching http://localhost:3033/login: HTTPConnectionPool(host='localhost', port=3033): Max retries exceeded with url: /login (Caused by NewConnectionError("HTTPConnection(host='localhost', port=3033): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))
[22:17:57] FAIL: Metrics Stack tests FAILED
[22:17:57] INFO: Running API Connectivity tests...
[22:17:57] PASS: Postman API: Using test placeholder - skipping live test
[22:17:57] PASS: Tailscale: Tailscale auth key not required for basic functionality
[22:17:57] PASS: API Connectivity tests PASSED
[22:17:57] INFO: Smoke tests completed: 4/11 passed
[22:17:57] FAIL: 7 tests failed - Check configuration
Installed 19 packages in 311ms
```

### PMOVES-BotZ-gateway (skip)
```text
No root-level deterministic test command found.
```

### Pmoves-cipher (pass)
```text
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mError Handling[2m > [22m[2mshould close page even if errors occur
[22m[39m22:18:25 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mError Handling[2m > [22m[2mshould close page even if errors occur
[22m[39m22:18:30 WARN: DuckDuckGo Puppeteer: Failed to fetch content for https://example.com/test:
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mBrowser Management[2m > [22m[2mshould reuse browser instance across searches
[22m[39m22:18:30 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mBrowser Management[2m > [22m[2mshould reuse browser instance across searches
[22m[39mDuckDuckGo Puppeteer search error: Error: Test error
    at [90m<WORKSTATION_PATH>\Pmoves-cipher\[39msrc\core\brain\tools\definitions\web-search\engine\__test__\duckduckgo.test.ts:467:40
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:155:11
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:752:26
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1897:20
    at new Promise (<anonymous>)
    at runWithTimeout [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1863:10[90m)[39m
    at runTest [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1574:12[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mBrowser Management[2m > [22m[2mshould reuse browser instance across searches
[22m[39mDuckDuckGo Puppeteer search error: Error: Test error
    at [90m<WORKSTATION_PATH>\Pmoves-cipher\[39msrc\core\brain\tools\definitions\web-search\engine\__test__\duckduckgo.test.ts:467:40
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:155:11
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:752:26
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1897:20
    at new Promise (<anonymous>)
    at runWithTimeout [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1863:10[90m)[39m
    at runTest [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1574:12[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mBrowser Management[2m > [22m[2mshould cleanup browser on cleanup call
[22m[39m22:18:36 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mBrowser Management[2m > [22m[2mshould cleanup browser on cleanup call
[22m[39mDuckDuckGo Puppeteer search error: Error: Test error
    at [90m<WORKSTATION_PATH>\Pmoves-cipher\[39msrc\core\brain\tools\definitions\web-search\engine\__test__\duckduckgo.test.ts:467:40
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:155:11
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:752:26
    at [90mfile:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1897:20
    at new Promise (<anonymous>)
    at runWithTimeout [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1863:10[90m)[39m
    at runTest [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1574:12[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
    at runSuite [90m(file:///<WORKSTATION_PATH>/Pmoves-cipher/[39mnode_modules/[4m.pnpm[24m/@vitest+runner@3.2.4/node_modules/[4m@vitest[24m/runner/dist/chunk-hooks.js:1729:8[90m)[39m
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mBrowser Management[2m > [22m[2mshould handle cleanup when no browser exists
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mUtility Methods[2m > [22m[2mshould sanitize queries correctly
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mUtility Methods[2m > [22m[2mshould sanitize queries correctly
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mUtility Methods[2m > [22m[2mshould build URLs correctly
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mUtility Methods[2m > [22m[2mshould build URLs correctly
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mConfiguration Updates[2m > [22m[2mshould allow configuration updates
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mConfiguration Updates[2m > [22m[2mshould provide statistics
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
[90mstderr[2m | src/core/brain/tools/definitions/web-search/engine/__test__/duckduckgo.test.ts[2m > [22m[2mDuckDuckGoPuppeteerProvider[2m > [22m[2mConfiguration Updates[2m > [22m[2mshould reset statistics
[22m[39m22:18:39 INFO: DuckDuckGo: Initialized for platform: linux (x64)
```

### PMOVES-HiRAG (skip)
```text
No root-level deterministic test command found.
```

### PMOVES-transcribe-and-fetch (fail)
```text
                          [36m>[39m
                            [36m<button[39m
                              [33maria-checked[39m=[32m"false"[39m
                              [33mclass[39m=[32m"peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"[39m
                              [33mdata-state[39m=[32m"unchecked"[39m
                              [33mid[39m=[32m"docType-Full Transcript"[39m
                              [33mrole[39m=[32m"checkbox"[39m
                              [33mtype[39m=[32m"button"[39m
                              [33mvalue[39m=[32m"on"[39m
                            [36m/>[39m
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
Time:        9.545 s
Ran all test suites.
```

### PMOVES-ToKenism-Multi (pass)
```text
..........................................                               [100%]
42 passed in 1.86s
```

### PMOVES-DoX (fail)
```text
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
backend\app\main.py:279
backend\app\main.py:279
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\main.py:279: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
    @app.on_event("startup")
..\..\..\..\AppData\Local\uv\cache\archive-v0\HvuA5oIP2jb_YBxFMpHe8\Lib\site-packages\fastapi\applications.py:4599
..\..\..\..\AppData\Local\uv\cache\archive-v0\HvuA5oIP2jb_YBxFMpHe8\Lib\site-packages\fastapi\applications.py:4599
  <WORKSTATION_CACHE>\archive-v0\HvuA5oIP2jb_YBxFMpHe8\Lib\site-packages\fastapi\applications.py:4599: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
    return self.router.on_event(event_type)
backend\app\services\reasoning_service.py:81
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\reasoning_service.py:81: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class ReasoningTrace(BaseModel):
backend\app\services\thread_manager.py:103
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\thread_manager.py:103: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class ThreadContext(BaseModel):
tests/test_agent_dispatcher.py::TestAgentInfo::test_agent_info_defaults
tests/test_agent_dispatcher.py::TestAgentInfo::test_agent_info_with_capabilities
tests/test_agent_dispatcher.py::TestDispatchResult::test_dispatch_result_creation
tests/test_agent_dispatcher.py::TestDispatchResult::test_mark_completed
tests/test_agent_dispatcher.py::TestDispatchResult::test_mark_failed
tests/test_agent_dispatcher.py::TestDispatchResult::test_mark_timeout
tests/test_agent_dispatcher.py::TestCachedAgent::test_cached_agent_creation
tests/test_agent_dispatcher.py::TestCachedAgent::test_is_expired_fresh
tests/test_agent_dispatcher.py::TestCachedAgent::test_is_expired_old
  <WORKSTATION_CACHE>\archive-v0\HvuA5oIP2jb_YBxFMpHe8\Lib\site-packages\pydantic\main.py:250: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
tests/test_agent_dispatcher.py::TestDispatchResult::test_mark_completed
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\agent_dispatcher.py:139: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    self.end_time = datetime.utcnow()
tests/test_agent_dispatcher.py::TestDispatchResult::test_mark_failed
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\agent_dispatcher.py:146: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    self.end_time = datetime.utcnow()
tests/test_agent_dispatcher.py::TestDispatchResult::test_mark_timeout
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\agent_dispatcher.py:153: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    self.end_time = datetime.utcnow()
tests/test_agent_dispatcher.py::TestCachedAgent::test_cached_agent_creation
tests/test_agent_dispatcher.py::TestCachedAgent::test_is_expired_fresh
tests/test_agent_dispatcher.py::TestCachedAgent::test_is_expired_old
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\agent_dispatcher.py:168: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    self.cached_at = datetime.utcnow()
tests/test_agent_dispatcher.py::TestCachedAgent::test_is_expired_fresh
tests/test_agent_dispatcher.py::TestCachedAgent::test_is_expired_old
  <WORKSTATION_PATH>\PMOVES-DoX\backend\app\services\agent_dispatcher.py:174: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow() >= self.expires_at
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED backend\tests\test_agent_dispatcher.py::TestAgentDispatcherInit::test_init_creates_empty_state
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 15 passed, 28 warnings in 11.68s
```

### PMOVES-Open-Notebook (pass)
```text
........................................................................ [ 73%]
..........................                                               [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\surreal_commands\core\retry.py:41
  <WORKSTATION_PATH>\PMOVES-Open-Notebook\.venv\Lib\site-packages\surreal_commands\core\retry.py:41: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class RetryConfig(BaseModel):
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
98 passed, 1 warning in 15.36s
warning: `VIRTUAL_ENV=<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
```

### PMOVES.YT (fail)
```text
============================= test session starts =============================
platform win32 -- Python 3.11.14, pytest-8.4.2, pluggy-1.6.0
rootdir: <WORKSTATION_PATH>\PMOVES.YT
configfile: pyproject.toml
collected 7418 items
test\test_InfoExtractor.py ....................                          [  0%]
test\test_YoutubeDL.py ............................                      [  0%]
test\test_YoutubeDLCookieJar.py .....                                    [  0%]
test\test_aes.py ............                                            [  0%]
test\test_age_restriction.py .F
================================== FAILURES ===================================
_______________________ TestAgeRestriction.test_youtube _______________________
self = <test.test_age_restriction.TestAgeRestriction testMethod=test_youtube>
    def test_youtube(self):
>       self._assert_restricted('HtVdAasjOgU', 'HtVdAasjOgU.mp4', 10)
test\test_age_restriction.py:46: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
test\test_age_restriction.py:42: in _assert_restricted
    self.assertTrue(_download_restricted(url, filename, old_age))
E   AssertionError: None is not true
---------------------------- Captured stdout call -----------------------------
[youtube] Extracting URL: HtVdAasjOgU
[youtube] HtVdAasjOgU: Downloading webpage
[youtube] HtVdAasjOgU: Downloading android vr player API JSON
[youtube] HtVdAasjOgU: This video is age-restricted; some formats may be missing without authentication. Use --cookies-from-browser or --cookies for the authentication. See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to manually pass cookies. Also see  https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies  for tips on effectively exporting YouTube cookies
[youtube] HtVdAasjOgU: Downloading web embedded client config
[youtube] HtVdAasjOgU: Downloading player 4eecba16-tv
[youtube] HtVdAasjOgU: Downloading web embedded player API JSON
[youtube] HtVdAasjOgU: Downloading web safari player API JSON
---------------------------- Captured stderr call -----------------------------
ERROR: [youtube] HtVdAasjOgU: Sign in to confirm your age. This video may be inappropriate for some users. Use --cookies-from-browser or --cookies for the authentication. See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to manually pass cookies. Also see  https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies  for tips on effectively exporting YouTube cookies
=========================== short test summary info ===========================
FAILED test/test_age_restriction.py::TestAgeRestriction::test_youtube - Asser...
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
======================== 1 failed, 66 passed in 11.36s ========================
warning: `VIRTUAL_ENV=<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
```