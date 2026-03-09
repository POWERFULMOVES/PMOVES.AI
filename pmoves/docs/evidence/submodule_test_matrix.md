# Submodule Test Matrix

- Generated: `2026-03-03 02:48 UTC`
- Total runs: **11**
- Results: **0 pass**, **11 fail**, **0 timeout**

| Submodule | Command | Status | Exit | Duration(s) |
| --- | --- | --- | --- | --- |
| `PMOVES-Agent-Zero` | `python -m pytest -q tests --maxfail=1` | `fail` | `1` | `0.08` |
| `PMOVES-Archon` | `make test-be` | `fail` | `2` | `9.68` |
| `PMOVES-BoTZ` | `make test-smoke` | `fail` | `2` | `0.58` |
| `PMOVES-BotZ-gateway` | `python -m pytest -q --maxfail=1` | `fail` | `1` | `0.08` |
| `Pmoves-cipher` | `npm run test -- --runInBand` | `fail` | `1` | `0.71` |
| `PMOVES-HiRAG` | `python -m pytest -q --maxfail=1` | `fail` | `1` | `0.07` |
| `PMOVES-transcribe-and-fetch` | `npm test -- --runInBand --watch=false` | `fail` | `1` | `12.42` |
| `PMOVES-ToKenism-Multi` | `python -m pytest -q tests --maxfail=1` | `fail` | `1` | `0.07` |
| `PMOVES-DoX` | `make test-standalone` | `fail` | `2` | `0.18` |
| `PMOVES-Open-Notebook` | `python -m pytest -q tests --maxfail=1` | `fail` | `1` | `0.07` |
| `PMOVES.YT` | `make test` | `fail` | `2` | `0.48` |

## Tails

### PMOVES-Agent-Zero (fail)
```text
<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv\Scripts\python.exe: No module named pytest
```

### PMOVES-Archon (fail)
```text
"Running backend tests..."
warning: `VIRTUAL_ENV=<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Using CPython 3.13.5
Creating virtual environment at: .venv
warning: `pypdfium2==4.30.1` is yanked (reason: "Text extraction regression in pdfium, crbug.com/387277993")
Downloading faker (1.9MiB)
Downloading mypy (9.1MiB)
Downloading ruff (12.3MiB)
 Downloading ruff
 Downloading faker
 Downloading mypy
Installed 23 packages in 1.78s
ImportError while loading conftest '<WORKSTATION_PATH>\PMOVES-Archon\python\tests\conftest.py'.
tests\conftest.py:7: in <module>
    from fastapi.testclient import TestClient
E   ModuleNotFoundError: No module named 'fastapi'
make: *** [Makefile:141: test-be] Error 4
```

### PMOVES-BoTZ (fail)
```text
"Running smoke tests..."
Traceback (most recent call last):
  File "<WORKSTATION_PATH>\PMOVES-BoTZ\scripts\smoke_tests.py", line 11, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'
make: *** [Makefile:171: test-smoke] Error 1
```

### PMOVES-BotZ-gateway (fail)
```text
<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv\Scripts\python.exe: No module named pytest
```

### Pmoves-cipher (fail)
```text
> @byterover/cipher@0.3.0 test
> vitest run --runInBand
file:///<WORKSTATION_PATH>/Pmoves-cipher/node_modules/.pnpm/vitest@3.2.4_@types+node@24.1.0_tsx@4.20.3_yaml@2.8.0/node_modules/vitest/dist/chunks/cac.Cb-PYCCB.js:404
          throw new CACError(`Unknown option \`${name.length > 1 ? `--${name}` : `-${name}`}\``);
                ^
CACError: Unknown option `--runInBand`
    at Command.checkUnknownOptions (file:///<WORKSTATION_PATH>/Pmoves-cipher/node_modules/.pnpm/vitest@3.2.4_@types+node@24.1.0_tsx@4.20.3_yaml@2.8.0/node_modules/vitest/dist/chunks/cac.Cb-PYCCB.js:404:17)
    at CAC.runMatchedCommand (file:///<WORKSTATION_PATH>/Pmoves-cipher/node_modules/.pnpm/vitest@3.2.4_@types+node@24.1.0_tsx@4.20.3_yaml@2.8.0/node_modules/vitest/dist/chunks/cac.Cb-PYCCB.js:604:13)
    at CAC.parse (file:///<WORKSTATION_PATH>/Pmoves-cipher/node_modules/.pnpm/vitest@3.2.4_@types+node@24.1.0_tsx@4.20.3_yaml@2.8.0/node_modules/vitest/dist/chunks/cac.Cb-PYCCB.js:545:12)
    at file:///<WORKSTATION_PATH>/Pmoves-cipher/node_modules/.pnpm/vitest@3.2.4_@types+node@24.1.0_tsx@4.20.3_yaml@2.8.0/node_modules/vitest/dist/cli.js:27:13
    at ModuleJob.run (node:internal/modules/esm/module_job:329:25)
    at async onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:644:26)
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:117:5)
Node.js v22.17.1
```

### PMOVES-HiRAG (fail)
```text
<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv\Scripts\python.exe: No module named pytest
```

### PMOVES-transcribe-and-fetch (fail)
```text
> pmoves-transcriber@0.1.0 test
> jest --runInBand --watch=false
```

### PMOVES-ToKenism-Multi (fail)
```text
<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv\Scripts\python.exe: No module named pytest
```

### PMOVES-DoX (fail)
```text
"Ensuring external networks exist for standalone mode..."
network was unexpected at this time.
make: *** [Makefile:54: ensure-standalone-networks] Error 255
```

### PMOVES-Open-Notebook (fail)
```text
<WORKSTATION_PATH>\pmoves-cipher-mcp\.venv\Scripts\python.exe: No module named pytest
```

### PMOVES.YT (fail)
```text
/usr/bin/env python3 -m pytest -Werror
The system cannot find the path specified.
"" was unexpected at this time.
'sed' is not recognized as an internal or external command,
operable program or batch file.
f was unexpected at this time.
'sed' is not recognized as an internal or external command,
operable program or batch file.
f was unexpected at this time.
File not found - *.py
process_begin: CreateProcess(NULL, sh.exe -c "/usr/bin/env python3 -m pytest -Werror", ...) failed.
make (e=2): The system cannot find the file specified.
make: *** [Makefile:84: test] Error 2
```