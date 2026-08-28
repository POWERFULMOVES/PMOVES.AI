#!/usr/bin/env python3
"""One-shot repair: collapse multi-line PEM/SSH values in env.shared to
single-line so Docker Compose's env-file parser stops choking on body lines.

Why this exists
---------------
Docker Compose's `--env-file` parser is strict: every non-comment line must be
`KEY=VALUE` and KEY must be a valid identifier (no `+`, `/`, `=` etc.). The
`secrets_local_hydrate.py` tool writes multi-line PEM keys (HOSTINGER_SSH_*,
GH_APP_SEC, etc.) raw — preserving the line breaks that come straight from
`$APPDATA/pmoves/secrets/local.env`. Python's iter-by-line consumers (which
include `_load_env_shared()` in tools/local_cert_runners.py) silently skip
the body lines as "no-equal", but Docker Compose errors out:

    failed to read env.shared: line 507: unexpected character "+" in
    variable name "t2+5bsdL/CVKMNeC8nyvAAA..."

Fix
---
For known multi-line key patterns (PEM headers/SSH key blocks), join the
value across continuation lines and write it back as a single line with
literal `\\n` escapes. Docker Compose treats `\\n` as a two-character
literal in env-file values, which is what services that consume PEM keys
(via env-var → write-to-tempfile pattern) expect.

Idempotent: if no multi-line values are detected, exits with no changes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns that indicate the start of a multi-line PEM/SSH block as the value
# of a KEY=VALUE line. We treat any line where the value begins with one of
# these markers as the start of a multi-line block, and fold subsequent lines
# (until matching END marker or blank line) into the same logical value.
PEM_START_MARKERS = (
    "-----BEGIN ",       # generic PEM
)
SSH_KEY_MARKERS = (
    "ssh-rsa ",
    "ssh-ed25519 ",
    "ssh-dss ",
    "ecdsa-sha2-",
)


def fix_env_shared(path: Path) -> tuple[int, int]:
    """Return (lines_before, lines_after). Re-writes path in place if needed."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    # Normalize line endings to LF for parsing; preserve content otherwise.
    src_lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    out: list[str] = []
    i = 0
    fixed_blocks = 0
    while i < len(src_lines):
        line = src_lines[i]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            out.append(line)
            i += 1
            continue
        key, val = m.group(1), m.group(2)
        # Treat the line as a multi-line block start whenever ANY of the next
        # non-blank/comment lines is NOT a valid KEY=VALUE — that means the
        # parser would error there. This catches bodies whose value-line did
        # not start with a recognized PEM/SSH marker (e.g. PEM was cleaned to
        # remove the BEGIN header, or value was truncated).
        peek = i + 1
        looks_multiline = False
        while peek < len(src_lines):
            nxt = src_lines[peek]
            if nxt.strip() == "" or nxt.lstrip().startswith("#"):
                break
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", nxt):
                break
            looks_multiline = True
            break
        if not looks_multiline:
            out.append(line)
            i += 1
            continue
        # Look ahead and absorb lines until we hit either an END marker (PEM)
        # or a line that looks like a new KEY=VALUE / blank / comment.
        body_parts = [val]
        j = i + 1
        while j < len(src_lines):
            nxt = src_lines[j]
            # New KEY= line means previous block ended.
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", nxt):
                break
            # Blank line ends the block.
            if nxt.strip() == "":
                # Don't consume the blank — let it stay as a separator.
                break
            # Comment lines also end the block (rare in PEM but safe).
            if nxt.lstrip().startswith("#"):
                break
            body_parts.append(nxt)
            # If the line is the END marker, consume it then stop.
            if nxt.startswith("-----END "):
                j += 1
                break
            j += 1
        if len(body_parts) == 1:
            # No continuation lines — pass through unchanged.
            out.append(line)
            i += 1
            continue
        # Join with literal \n (two chars) so Docker env-file parsing stays
        # within a single value. Consumers that need real newlines must
        # decode \n → \n at use time (most PEM consumers via base64-decode
        # or tempfile write handle this naturally; if not, the consumer
        # is the one to fix, not the storage format).
        joined = "\\n".join(body_parts)
        out.append(f"{key}={joined}")
        fixed_blocks += 1
        i = j

    if fixed_blocks == 0:
        print(f"No multi-line PEM/SSH blocks detected in {path}. No changes.")
        return len(src_lines), len(src_lines)

    new_text = "\n".join(out)
    if not new_text.endswith("\n"):
        new_text += "\n"
    # Backup before overwrite (sibling .bak with timestamp suffix).
    import time
    bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    bak.write_text(raw, encoding="utf-8")
    path.write_text(new_text, encoding="utf-8")
    print(f"Fixed {fixed_blocks} multi-line block(s) in {path}.")
    print(f"Backup: {bak}")
    return len(src_lines), len(out)


def main() -> int:
    """Entry point: locate env.shared and repair multi-line values."""
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "pmoves" / "env.shared"
    if not env_path.exists():
        print(f"env.shared not found at {env_path}", file=sys.stderr)
        return 1
    before, after = fix_env_shared(env_path)
    print(f"Lines: {before} -> {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
