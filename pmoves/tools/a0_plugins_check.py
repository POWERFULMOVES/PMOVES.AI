"""Validate local Agent Zero plugin catalog entries for a0-plugins submissions.

Checks mirror the upstream a0-plugins validator:
- plugin.yaml required
- allowed/required fields
- title/description/tag limits
- GitHub URL format

Optional remote checks can verify each target repository exists and contains a
root plugin.yaml on its default branch.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ALLOWED_KEYS = {"title", "description", "github", "tags"}
REQUIRED_KEYS = {"title", "description", "github"}
MAX_TITLE_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 500
MAX_TAGS = 5
GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except Exception as exc:  # pragma: no cover - error handling path
        raise ValueError(f"invalid YAML ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError("plugin.yaml must contain a mapping/object")
    return data


def _validate_fields(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    keys = set(data.keys())
    extra = sorted(keys - ALLOWED_KEYS)
    missing = sorted(REQUIRED_KEYS - keys)
    if extra:
        errors.append(f"unsupported fields: {extra}")
    if missing:
        errors.append(f"missing required fields: {missing}")

    title = data.get("title")
    desc = data.get("description")
    github = data.get("github")

    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"title must be <= {MAX_TITLE_LENGTH} chars")

    if not isinstance(desc, str) or not desc.strip():
        errors.append("description must be a non-empty string")
    elif len(desc) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"description must be <= {MAX_DESCRIPTION_LENGTH} chars")

    if not isinstance(github, str) or not github.strip():
        errors.append("github must be a non-empty string")
    elif not GITHUB_RE.match(github.strip()):
        errors.append("github must be a GitHub repository URL")

    tags = data.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() for t in tags):
            errors.append("tags must be a list of non-empty strings")
        elif len(tags) > MAX_TAGS:
            errors.append(f"tags must have at most {MAX_TAGS} entries")

    return errors


def _github_api_get(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "pmoves-a0-plugins-check",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("GitHub API returned non-object JSON")
    return data


def _remote_check(github_url: str, token: str | None) -> list[str]:
    errors: list[str] = []
    m = GITHUB_RE.match(github_url.strip())
    if not m:
        return ["github URL does not match expected pattern"]

    owner, repo = m.group(1), m.group(2)
    try:
        repo_info = _github_api_get(f"https://api.github.com/repos/{owner}/{repo}", token)
        default_branch = repo_info.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch.strip():
            return ["unable to resolve default_branch via GitHub API"]
        _github_api_get(
            "https://api.github.com/repos/"
            f"{owner}/{repo}/contents/plugin.yaml?ref={urllib.parse.quote(default_branch)}",
            token,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        errors.append(f"remote check failed ({exc.code}): {body[:300]}")
    except Exception as exc:  # pragma: no cover - network error path
        errors.append(f"remote check failed: {exc}")
    return errors


def _iter_plugin_yaml_files(catalog_root: Path) -> list[Path]:
    if not catalog_root.exists():
        return []
    return sorted(catalog_root.glob("*/plugin.yaml"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PMOVES a0-plugin catalog.")
    parser.add_argument(
        "--catalog-root",
        default="pmoves/integrations/agent0-plugins/catalog",
        help="Catalog root containing plugin subfolders (default: %(default)s)",
    )
    parser.add_argument(
        "--require-remote",
        action="store_true",
        help="Require GitHub remote checks for each plugin repository.",
    )
    args = parser.parse_args()

    catalog_root = Path(args.catalog_root)
    plugin_files = _iter_plugin_yaml_files(catalog_root)
    if not plugin_files:
        print(f"ERROR no plugin.yaml files found under {catalog_root}")
        return 2

    token = None
    if args.require_remote:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    total_errors = 0
    for plugin_yaml in plugin_files:
        rel = plugin_yaml.as_posix()
        errs: list[str] = []
        try:
            data = _load_yaml(plugin_yaml)
            errs.extend(_validate_fields(data))
            if args.require_remote and isinstance(data.get("github"), str):
                errs.extend(_remote_check(data["github"], token))
        except Exception as exc:
            errs.append(str(exc))

        if errs:
            total_errors += len(errs)
            print(f"FAIL {rel}")
            for err in errs:
                print(f"  - {err}")
        else:
            print(f"OK   {rel}")

    if total_errors:
        print(f"Validation failed with {total_errors} error(s).")
        return 1
    print(f"Validation passed for {len(plugin_files)} plugin(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
