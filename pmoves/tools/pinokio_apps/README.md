# pmoves/tools/pinokio_apps

The discover tool (`discover.py`) walks a Pinokio install dir
(`~/pinokio/api/`, or `D:\pinokio\api\` on Windows) and generates
registry entries in `pmoves/configs/pinokio-apps/user/<slug>.yaml`
for every app that doesn't already have one in `curated/`.

Slice 4 of the creator-collab lane. The companion to
`pmoves/services/mesh_exposure/` (which reads the registry) and
`pmoves/skills/gepeto-wrapper-skill/` (the PMOVES-side surface for
the registry).

## Usage

```bash
# Default: scan the OS-default Pinokio home (~/pinokio on mac/linux, D:\pinokio on Windows)
cd pmoves
python tools/pinokio_apps/discover.py

# Custom Pinokio home
python tools/pinokio_apps/discover.py --pinokio-home /custom/pinokio

# Custom curated + user dirs
python tools/pinokio_apps/discover.py \
  --registry-dir /path/to/curated \
  --user-dir /path/to/user

# Dry-run (print the entries, don't write to disk)
python tools/pinokio_apps/discover.py --dry-run
```

## Behavior

- Walks `pinokio_home/api/<slug>/` for every subdir
- Reads `<slug>/pinokio.js` (or `pinokio.json` / `pinokio.yml`) as the
  launcher manifest; tolerates JS-style comments + trailing commas
- Falls back to `version.json` (or `package.json`) for the version
- Skips entries already in `curated/` (or `user/`) — never overwrites
- Validates every generated entry against
  `pmoves/configs/pinokio-apps/schema/pinokio-app.v1.schema.json`
  before writing; bad entries are reported, not written
- Prints a summary + exits non-zero on any validation error (so the
  CI cron + the operator's runbook both notice)

## Output

```
discover.py summary
  pinokio_home:    D:\pinokio
  existing slugs:  12 (curated + user)
  scanned apps:    23
  new entries:     9
  validation errs: 2

New entries:
  + pmoves/configs/pinokio-apps/user/comfyui-desktop.yaml
  + pmoves/configs/pinokio-apps/user/ace-step.yaml
  ...
```

## Promotion workflow

`discover.py` writes to `user/` by default. To promote an entry to
`curated/`:

1. **Review** the generated YAML (some fields are best-guess — e.g. the
   `runtime.gpu_required` may default to `false` if the manifest
   doesn't declare it)
2. **Correct** any wrong fields manually
3. **Validate** with the gepeto-wrapper skill: `pmoves registry validate --slug <slug>`
4. **Promote** with the gepeto-wrapper skill: `pmoves registry promote --slug <slug>`
   (or copy the file manually + update the `notes` block)
5. **Delete** the `user/` copy once the curated copy is verified

## Test surface

```bash
cd pmoves
python -m pytest tools/pinokio_apps/tests/ -q
```

19 pytest cases. Uses `tmp_path` for the fake Pinokio home + the
live registry schema. No real Pinokio install required.
