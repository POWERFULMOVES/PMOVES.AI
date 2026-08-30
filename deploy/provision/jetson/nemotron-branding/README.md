# Nemotron / NemoClaw Branding Assets

Branding files applied by `../post-flash-bootstrap.sh` after a Jetson
JetPack 7.0 reflash. These are the customer-facing surfaces when UNFCU
(enterprise client) demos or inspects the device.

## Files

| File | Purpose |
|------|---------|
| `motd.txt` | `/etc/motd` — shown on every SSH login and local terminal login |
| `plymouth-theme/` | Boot splash (copied to `/usr/share/plymouth/themes/nemotron/`) |
| `README.md` | This file |

## Placeholder substitution

`motd.txt` uses `${DEVICE}` as a placeholder; `post-flash-bootstrap.sh`
expands it to the actual device name (`nemotron-1` or `nemotron-2`) at
install time via `sed`.

## Plymouth theme

The theme directory (when populated) should contain:
- `nemotron.plymouth` — theme manifest (script plugin)
- `nemotron.script` — optional animation script
- Assets: PNG splash with NVIDIA green (#76B900) + PMOVES brand purple (#7C3AED)

**Current state:** directory exists but is empty. When UNFCU presentation
assets are finalized, drop the PNG/script files here and the post-flash
script will pick them up automatically.

## Invocation

```bash
# Applied automatically during post-flash
sudo DEVICE=nemotron-1 bash ../post-flash-bootstrap.sh

# Manually re-apply (e.g. after a cosmetic update)
sudo cp motd.txt /etc/motd
sudo sed -i "s/\${DEVICE}/$(hostname)/g" /etc/motd
```

## See also

- Memory: `project_jetson_nemotron_unfcu.md` — client context
- Memory: `project_unfcu_dox.md` — UNFCU bid context
- `../README.md` — Jetson reflash runbook
