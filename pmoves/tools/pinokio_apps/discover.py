"""discover.py — scan a Pinokio install dir, generate registry entries.

Slice 4 of the creator-collab lane. Reads `~/pinokio/api/` (or
`D:\\pinokio\\api\\` on Windows) and generates
`pmoves/configs/pinokio-apps/user/<slug>.yaml` for every installed app
that doesn't already have a curated entry.

The tool is intentionally conservative:
  - it never overwrites curated entries
  - it validates every generated entry against the schema before
    writing (a bad pinokio.js + good defaults = still rejected)
  - it prints a summary + exits non-zero if anything failed (so the
    CI cron + the operator's runbook both notice)

Usage:
  python pmoves/tools/pinokio_apps/discover.py
  python pmoves/tools/pinokio_apps/discover.py --pinokio-home /custom/pinokio
  python pmoves/tools/pinokio_apps/discover.py --registry-dir /custom/registry --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from jsonschema import Draft202012Validator, FormatChecker

# Repo-relative path resolution. The tool lives at
# pmoves/tools/pinokio_apps/discover.py; the registry lives at
# pmoves/configs/pinokio-apps/.
DEFAULT_REGISTRY_DIR = "pmoves/configs/pinokio-apps/curated"
DEFAULT_USER_DIR = "pmoves/configs/pinokio-apps/user"
SCHEMA_PATH = "pmoves/configs/pinokio-apps/schema/pinokio-app.v1.schema.json"
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def default_pinokio_home() -> str:
    """Return the OS-default Pinokio home path.

    Windows: D:\\pinokio (the 5090 host convention)
    macOS:   ~/pinokio
    Linux:   ~/pinokio
    Override via --pinokio-home or PINOKIO_HOME env var."""
    env = os.environ.get("PINOKIO_HOME", "").strip()
    if env:
        return env
    if platform.system() == "Windows":
        return r"D:\pinokio"
    return str(Path.home() / "pinokio")


def load_schema() -> Draft202012Validator:
    """Load the registry JSON Schema as a Draft 2020-12 validator."""
    path = Path(SCHEMA_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Schema not found at {path}")
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def load_existing_slugs(registry_dir: str) -> set:
    """Slugs already covered by curated/ (and any pre-existing user/)."""
    out = set()
    for d in (Path(registry_dir), Path(DEFAULT_USER_DIR)):
        if d.exists():
            for f in d.glob("*.yaml"):
                if not f.stem.startswith("."):
                    out.add(f.stem)
    return out


def read_pinokio_manifest(api_dir: Path) -> Optional[Dict[str, Any]]:
    """Read a Pinokio app's launcher JSON (pinokio.js or pinokio.json).

    Returns the parsed dict, or None if no manifest is found. Tolerates
    JSONC-style comments + trailing commas (Pinokio's pinokio.js often
    uses a JS-evaluated JSON that doesn't quite parse as strict JSON)."""
    for name in ("pinokio.js", "pinokio.json", "pinokio.yml", "pinokio.yaml"):
        p = api_dir / name
        if p.exists():
            text = p.read_text()
            # Strip JS-style line comments
            text = re.sub(r"//[^\n]*", "", text)
            # Strip block comments
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
            # Strip trailing commas before } or ]
            text = re.sub(r",(\s*[}\]])", r"\1", text)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                logging.warning("failed to parse %s: %s", p, e)
                return None
    return None


def detect_endpoints(manifest: Optional[Dict[str, Any]], api_dir: Path) -> Dict[str, Any]:
    """Best-effort: extract a primary endpoint from the manifest.

    Many Pinokio launchers declare a "start" script with no explicit
    port; the bridge reads the actual port from
    ~/pinokio/api/<slug>/<port_file> or from the running process. Here
    we default to port=0 (dynamic) and let the bridge resolve it."""
    primary_port = 0
    primary_protocol = "http"
    health = None
    if isinstance(manifest, dict):
        # P8+ manifest shape may include a `port` or `endpoints` field.
        if isinstance(manifest.get("port"), int):
            primary_port = manifest["port"]
        ep = manifest.get("endpoints")
        if isinstance(ep, list) and ep:
            entry = ep[0]
            if isinstance(entry, dict):
                if isinstance(entry.get("port"), int):
                    primary_port = entry["port"]
                if entry.get("protocol") in {"http", "https", "ws", "wss", "grpc", "tcp"}:
                    primary_protocol = entry["protocol"]
                if isinstance(entry.get("health"), str):
                    health = entry["health"]
    return {"primary": {"port": primary_port, "protocol": primary_protocol, "health": health}, "alt": []}


def detect_hardware(manifest: Optional[Dict[str, Any]], api_dir: Path) -> Dict[str, Any]:
    """Best-effort: extract GPU/VRAM facts from the manifest.

    The bridge /v1/gpu/detect is the runtime source of truth; the
    registry only declares the *minimum* the app declares in its own
    manifest. If the manifest has nothing, we default to CPU-only."""
    gpu_required = False
    min_vram_mb = 0
    gpu_arch: List[str] = []
    if isinstance(manifest, dict):
        req = manifest.get("requirements") or {}
        if isinstance(req, dict):
            if req.get("gpu"):
                gpu_required = True
            v = req.get("vram_mb")
            if isinstance(v, int):
                min_vram_mb = v
            arch = req.get("gpu_arch")
            if isinstance(arch, list):
                gpu_arch = [a for a in arch if isinstance(a, str)]
    return {
        "launcher_script": (manifest or {}).get("start_script", "start.js") if isinstance(manifest, dict) else "start.js",
        "autostart": False,
        "gpu_required": gpu_required,
        "min_vram_mb": min_vram_mb,
        "gpu_arch": gpu_arch,
        "gpu_reservation_mb": min_vram_mb,
        "gpu_reservation_mode": "concurrent",
        "dependencies": [],
        "requires_hf_login": False,
    }


def detect_p8_skill(manifest: Optional[Dict[str, Any]]) -> Optional[str]:
    """If the manifest declares a managed skill slug, return it."""
    if isinstance(manifest, dict):
        sk = manifest.get("skill") or manifest.get("p8_skill")
        if isinstance(sk, str) and SLUG_PATTERN.match(sk):
            return sk
    return None


def detect_version(api_dir: Path) -> str:
    """Best-effort: read version.json or package.json's version field."""
    for name, key in (("version.json", "version"), ("package.json", "version")):
        p = api_dir / name
        if p.exists():
            try:
                data = json.loads(p.read_text())
                v = data.get(key)
                if isinstance(v, str):
                    return v
            except (json.JSONDecodeError, OSError):
                pass
    return "0.0.0-unknown"


def build_entry(api_dir: Path, manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a complete registry entry for one Pinokio app.

    The output is a fully-populated dict that the schema accepts. The
    operator can promote user/ entries to curated/ after review."""
    slug = api_dir.name
    if not SLUG_PATTERN.match(slug):
        raise ValueError(f"invalid slug: {slug!r}")
    title = (manifest or {}).get("title") or slug
    if isinstance(title, str):
        title = title.strip()
    else:
        title = slug
    description = (manifest or {}).get("description") or f"Discovered Pinokio app at {api_dir}"
    if not isinstance(description, str):
        description = str(description)
    description = description[:512]  # schema has no maxLength; keep it sane
    return {
        "schema_version": "1.0.0",
        "slug": slug,
        "title": title,
        "description": description,
        "owner": "pinokio",
        "version_seen": detect_version(api_dir),
        "runtime": detect_hardware(manifest, api_dir),
        "endpoints": detect_endpoints(manifest, api_dir),
        "pinokio_skill_ref": detect_p8_skill(manifest),
        "network_exposure": {
            "l1_venv": {"reachable": True},
            "l2_container_same_host": {"reachable": True, "address": None},
            "l3_mesh": {"reachable": False, "address": None, "headscale_acl_ports": [], "tags_required": []},
            "l4_public": {"reachable": False, "tunnel": None, "dns_record": None, "public_url": None},
        },
        "notes": [
            f"auto-generated by discover.py from {api_dir}",
            "review + promote to curated/ after operator check",
        ],
    }


def discover(
    pinokio_home: str,
    existing_slugs: set,
    validator: Draft202012Validator,
) -> Tuple[List[Dict[str, Any]], List[Path], List[Tuple[Path, str]]]:
    """Walk pinokio_home/api/, build entries for new apps, validate.

    Returns: (entries_to_write, source_dirs, validation_errors)
    Validation errors are non-fatal — they're collected so the operator
    can see them all in one run."""
    api_dir = Path(pinokio_home) / "api"
    if not api_dir.is_dir():
        raise FileNotFoundError(f"Pinokio api dir not found: {api_dir}")

    entries: List[Dict[str, Any]] = []
    source_dirs: List[Path] = []
    errors: List[Tuple[Path, str]] = []

    for sub in sorted(api_dir.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name.startswith("."):
            continue
        if sub.name in existing_slugs:
            logging.info("skip %s (already in registry)", sub.name)
            continue
        manifest = read_pinokio_manifest(sub)
        try:
            entry = build_entry(sub, manifest)
        except (ValueError, Exception) as e:  # noqa: BLE001
            errors.append((sub, f"build: {e}"))
            continue
        errs = list(validator.iter_errors(entry))
        if errs:
            first = errs[0]
            errors.append((sub, f"validate: {first.message} at {list(first.absolute_path)}"))
            continue
        entries.append(entry)
        source_dirs.append(sub)
    return entries, source_dirs, errors


def write_entries(entries: List[Dict[str, Any]], user_dir: str, dry_run: bool) -> List[Path]:
    """Write the generated entries to user_dir. Returns the paths written."""
    p = Path(user_dir)
    if not dry_run:
        p.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for entry in entries:
        path = p / f"{entry['slug']}.yaml"
        if not dry_run:
            path.write_text(yaml.safe_dump(entry, sort_keys=False))
        written.append(path)
    return written


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    ap = argparse.ArgumentParser(
        description="Discover installed Pinokio apps and generate registry entries in user/."
    )
    ap.add_argument("--pinokio-home", default=default_pinokio_home(),
                    help="Pinokio home dir (default: %(default)s)")
    ap.add_argument("--registry-dir", default=DEFAULT_REGISTRY_DIR,
                    help="Curated registry dir (default: %(default)s)")
    ap.add_argument("--user-dir", default=DEFAULT_USER_DIR,
                    help="User registry dir (default: %(default)s)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the generated entries without writing to disk.")
    args = ap.parse_args(argv)

    try:
        validator = load_schema()
    except FileNotFoundError as e:
        logging.error("%s; run from the repo root or update SCHEMA_PATH", e)
        return 2

    existing = load_existing_slugs(args.registry_dir)
    logging.info("existing slugs: %d", len(existing))

    try:
        entries, source_dirs, errors = discover(args.pinokio_home, existing, validator)
    except FileNotFoundError as e:
        logging.error("%s", e)
        return 2

    written = write_entries(entries, args.user_dir, dry_run=args.dry_run)

    print("\ndiscover.py summary")
    print(f"  pinokio_home:    {args.pinokio_home}")
    print(f"  existing slugs:  {len(existing)} (curated + user)")
    print(f"  scanned apps:    {len(source_dirs) + len(errors)}")
    print(f"  new entries:     {len(written)}")
    print(f"  validation errs: {len(errors)}")
    if args.dry_run:
        print("  mode:            DRY RUN (no files written)")
    print()
    if written:
        print("New entries:")
        for p in written:
            print(f"  + {p}")
    if errors:
        print("\nValidation errors (entries NOT written):")
        for path, msg in errors:
            print(f"  ! {path}: {msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
