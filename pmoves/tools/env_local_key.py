#!/usr/bin/env python3
"""Set, unset or test ONE key in the node-local overlay env file. Operator-run.

THE KNOWN ROAD FOR ENV.LOCAL KEY EDITS
======================================

`pmoves/.env.local` is the node-local overlay `scripts/with-env.sh` loads after
the generated tier files. Nothing generates it, so until this tool existed the
only way to change it was by hand -- and a hand edit leaves no record. That is
how `CIPHER_DB_SERVICE_KEY=${SERVICE_ROLE_KEY}` reached a node: copied from a
recipe in a commit message (df0218537), with no audit row, and later pointing
at a key Kong rejects. The operator asked for the reverse edit to travel "the
same way it was placed", on a road. This is that road, for both directions.

WHO RUNS IT
-----------
The OPERATOR, through `make -C pmoves env-local-{set,unset,has} KEY=...`.
Agents keep ZERO access to the file; the damage-control zero-access rule is
unchanged by this tool. Agents may run it only against temp files they
created, via `--file` (which is how the tests run it).

WHAT IT GUARANTEES
------------------
* Exactly one key, spelled `^[A-Z][A-Z0-9_]*$`. Anything else is refused.
* It never prints, logs or audits a VALUE. Output is key, action, whether a
  line existed, and the old/new value LENGTH.
* `set` reads the value from stdin (or a no-echo prompt when stdin is a TTY),
  never argv -- so the value is not in shell history or `ps`.
* A key that appears more than once is refused (the count is reported): the
  loader would take the last one, and "which one did you mean" is a question
  for the operator, not a guess for the tool.
* Before any change the file is copied to `<file>.bak-<UTC ts>`, mode 0600.
* The write is atomic (temp file in the same directory, fsync, rename) and the
  file's mode is preserved (0600 for a file this tool creates).
* Every other line is preserved byte-for-byte, comments and line endings
  included.
* Each completed set/unset appends one row to a git-ignored local audit log
  (`pmoves/data/audit/env_local_edits.jsonl`): ts, host, key, action,
  old_len, new_len, operator, line_existed, changed, backup. Never the value.

EXIT CODES
----------
  0  done (for `has`: the key is present exactly once)
  1  refused (malformed key, duplicate key, empty or multi-line value) --
     or, for `has`, the key is absent
  2  usage error
  3  could not measure (file missing for unset/has, unreadable, I/O error)

Note that `make` collapses every nonzero recipe exit to 2; read the printed
`result=` line, not make's exit code.

Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import getpass
import json
import os
import re
import socket
import stat
import sys
import tempfile
from pathlib import Path

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

PMOVES_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FILE = PMOVES_DIR / ".env.local"
DEFAULT_AUDIT = PMOVES_DIR / "data" / "audit" / "env_local_edits.jsonl"
# Overrides for tests that drive the MAKE TARGETS (which pass no --file). The
# resolved path is always printed, so a stray override cannot redirect an
# operator's edit silently.
FILE_ENV = "ENV_LOCAL_KEY_FILE"
AUDIT_ENV = "ENV_LOCAL_KEY_AUDIT"

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_UNMEASURABLE = 3


class Refused(Exception):
    """The request is well-formed enough to parse but must not be applied."""


class Unmeasurable(Exception):
    """The file cannot be read or written, so no verdict can be given."""


def _line_re(key: str) -> "re.Pattern[bytes]":
    # A superset of what with-env.sh loads (`^KEY[[:space:]]*=`): leading
    # whitespace and an `export ` prefix are ignored by the loader, but a line
    # in either shape is still a definition an operator would call "the
    # line", so it counts toward duplicate detection and is what unset removes.
    return re.compile(rb"^[ \t]*(?:export[ \t]+)?" + re.escape(key.encode()) + rb"[ \t]*=")


def _value_len(line: bytes) -> int:
    """Length (in characters) of the raw text after the first `=`, sans EOL."""
    body = line.rstrip(b"\r\n")
    raw = body.split(b"=", 1)[1] if b"=" in body else b""
    return len(raw.decode("utf-8", errors="replace"))


def _eol(line: bytes) -> bytes:
    if line.endswith(b"\r\n"):
        return b"\r\n"
    if line.endswith(b"\n"):
        return b"\n"
    return b""


def _utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:  # permission, is-a-directory, ...
        raise Unmeasurable(f"cannot read file: {exc.__class__.__name__}") from exc


def _find(lines: list[bytes], key: str) -> list[int]:
    pat = _line_re(key)
    return [i for i, ln in enumerate(lines) if pat.match(ln)]


def _backup(path: Path, data: bytes) -> Path:
    stamp = _utc_stamp()
    for n in range(100):
        suffix = f".bak-{stamp}" if n == 0 else f".bak-{stamp}-{n}"
        bak = path.with_name(path.name + suffix)
        try:
            fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        except BaseException:
            try:
                bak.unlink()
            except OSError:
                pass
            raise
        return bak
    raise Unmeasurable("could not allocate a unique backup name")


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _audit(audit_path: Path, row: dict) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(audit_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _report(**fields: object) -> None:
    order = ["result", "key", "action", "line_existed", "count", "old_len",
             "new_len", "changed", "backup", "file", "audit"]
    parts = []
    for k in order:
        if k in fields:
            v = fields[k]
            if isinstance(v, bool):
                v = "yes" if v else "no"
            parts.append(f"{k}={'-' if v is None else v}")
    print("env-local-key: " + " ".join(parts))


def _read_value(stdin, key: str) -> bytes:
    if stdin.isatty():
        # No-echo prompt on the controlling terminal. This is what `read -s`
        # would do, without the value ever becoming a shell variable -- and
        # make's recipe shell is /bin/sh, where `read -s` does not exist.
        text = getpass.getpass(f"value for {key} (hidden, not echoed): ")
    else:
        text = stdin.read()
    # Strip exactly one trailing newline (a piped `echo` or a heredoc).
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    if text == "":
        raise Refused("empty value refused; use unset to remove a key")
    if "\n" in text or "\r" in text:
        raise Refused("multi-line value refused")
    return text.encode("utf-8")


def _row(key: str, action: str, **extra: object) -> dict:
    row = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "key": key,
        "action": action,
        "operator": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
    }
    row.update(extra)
    return row


def cmd_has(path: Path, key: str) -> int:
    data = _read(path)
    if data is None:
        raise Unmeasurable("file does not exist")
    idx = _find(data.splitlines(keepends=True), key)
    if len(idx) > 1:
        _report(result="refused", key=key, action="has", line_existed=True,
                count=len(idx), file=path)
        print(f"env-local-key: refused: {key} appears {len(idx)} times",
              file=sys.stderr)
        return EXIT_REFUSED
    present = len(idx) == 1
    _report(result="present" if present else "absent", key=key, action="has",
            line_existed=present, count=len(idx),
            old_len=_value_len(data.splitlines(keepends=True)[idx[0]]) if present else None,
            file=path)
    return EXIT_OK if present else EXIT_REFUSED


def cmd_unset(path: Path, key: str, audit_path: Path) -> int:
    data = _read(path)
    if data is None:
        raise Unmeasurable("file does not exist")
    lines = data.splitlines(keepends=True)
    idx = _find(lines, key)
    if len(idx) > 1:
        raise Refused(f"{key} appears {len(idx)} times; resolve by hand-review, not by guess")
    if not idx:
        _audit(audit_path, _row(key, "unset", old_len=None, new_len=None,
                                line_existed=False, changed=False, backup=None))
        _report(result="noop", key=key, action="unset", line_existed=False,
                old_len=None, new_len=None, changed=False, file=path,
                audit=audit_path)
        return EXIT_OK
    i = idx[0]
    old_len = _value_len(lines[i])
    mode = stat.S_IMODE(path.stat().st_mode)
    bak = _backup(path, data)
    new = b"".join(lines[:i] + lines[i + 1:])
    _atomic_write(path, new, mode)
    _audit(audit_path, _row(key, "unset", old_len=old_len, new_len=None,
                            line_existed=True, changed=True, backup=bak.name))
    _report(result="done", key=key, action="unset", line_existed=True,
            old_len=old_len, new_len=None, changed=True, backup=bak.name,
            file=path, audit=audit_path)
    return EXIT_OK


def cmd_set(path: Path, key: str, audit_path: Path, stdin) -> int:
    data = _read(path)
    value = _read_value(stdin, key)
    new_line_body = key.encode() + b"=" + value
    bak_name = None
    if data is None:
        new = new_line_body + b"\n"
        mode = 0o600
        existed = False
        old_len = None
    else:
        lines = data.splitlines(keepends=True)
        idx = _find(lines, key)
        if len(idx) > 1:
            raise Refused(f"{key} appears {len(idx)} times; resolve by hand-review, not by guess")
        mode = stat.S_IMODE(path.stat().st_mode)
        if idx:
            i = idx[0]
            existed = True
            old_len = _value_len(lines[i])
            prefix = b"export " if re.match(rb"^[ \t]*export[ \t]", lines[i]) else b""
            eol = _eol(lines[i]) or b""
            lines[i] = prefix + new_line_body + eol
            new = b"".join(lines)
        else:
            existed = False
            old_len = None
            sep = b"" if (not data or data.endswith(b"\n")) else b"\n"
            new = data + sep + new_line_body + b"\n"
        bak_name = _backup(path, data).name
    _atomic_write(path, new, mode)
    new_len = len(value.decode("utf-8"))
    _audit(audit_path, _row(key, "set", old_len=old_len, new_len=new_len,
                            line_existed=existed, changed=True, backup=bak_name))
    _report(result="done", key=key, action="set", line_existed=existed,
            old_len=old_len, new_len=new_len, changed=True, backup=bak_name,
            file=path, audit=audit_path)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="env_local_key.py",
        description="Set/unset/test ONE key in the node-local env overlay. "
                    "Never prints values. Operator-run.")
    p.add_argument("--file", type=Path,
                   default=Path(os.environ[FILE_ENV]) if os.environ.get(FILE_ENV) else DEFAULT_FILE,
                   help="file to edit (default: the pmoves node-local overlay). "
                        "Tests pass a temp file here.")
    p.add_argument("--audit-log", type=Path,
                   default=Path(os.environ[AUDIT_ENV]) if os.environ.get(AUDIT_ENV) else DEFAULT_AUDIT,
                   help="local, git-ignored JSONL audit log")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("set", "set KEY; value is read from stdin"),
                           ("unset", "remove the single KEY line"),
                           ("has", "report whether KEY is present (no value)")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("key")
    return p


def main(argv: list[str] | None = None, stdin=None) -> int:
    args = build_parser().parse_args(argv)
    stdin = stdin if stdin is not None else sys.stdin
    key = args.key
    if not KEY_RE.match(key):
        # Do not echo the rejected text: it may be a value pasted by mistake.
        print(f"env-local-key: result=refused action={args.cmd} "
              f"reason=malformed-key key_len={len(key)} (need ^[A-Z][A-Z0-9_]*$)",
              file=sys.stderr)
        return EXIT_REFUSED
    try:
        if args.cmd == "has":
            return cmd_has(args.file, key)
        if args.cmd == "unset":
            return cmd_unset(args.file, key, args.audit_log)
        return cmd_set(args.file, key, args.audit_log, stdin)
    except Refused as exc:
        print(f"env-local-key: result=refused key={key} action={args.cmd} reason={exc}",
              file=sys.stderr)
        return EXIT_REFUSED
    except Unmeasurable as exc:
        print(f"env-local-key: result=could-not-measure key={key} action={args.cmd} "
              f"reason={exc}", file=sys.stderr)
        return EXIT_UNMEASURABLE
    except OSError as exc:
        print(f"env-local-key: result=could-not-measure key={key} action={args.cmd} "
              f"reason={exc.__class__.__name__}", file=sys.stderr)
        return EXIT_UNMEASURABLE


if __name__ == "__main__":
    sys.exit(main())
