#!/usr/bin/env python3
"""Set, unset or test ONE key in the node-local overlay env file. Operator-run.

THE KNOWN ROAD FOR ENV.LOCAL KEY EDITS
======================================

`pmoves/.env.local` is the node-local overlay `scripts/with-env.sh` loads after
the generated tier files. Nothing generates it, so until this tool existed the
only way to change it was by hand -- and a hand edit leaves no record. That is
how `CIPHER_DB_SERVICE_KEY=${SERVICE_ROLE_KEY}` reached a fleet node: copied
from a recipe in a commit message (df0218537), with no audit row, and later
pointing at a key Kong rejects. The operator asked for the reverse edit to
travel "the same way it was placed", on a road. This is that road, for both
directions.

WHO RUNS IT
-----------
The OPERATOR, through `make -C pmoves env-local-{set,unset,has} KEY=...`.
Agents keep ZERO access to the file; the damage-control zero-access rule is
unchanged by this tool. Agents may run it only against temp files they
created, via `--file` (which is how the tests run it). Under pytest
(`PYTEST_CURRENT_TEST` set) the tool refuses to act on the default path at all.

WHAT COUNTS AS A DEFINITION -- the loader's rule, not a looser one
------------------------------------------------------------------
with-env.sh loads only lines matching `^NAME[[:space:]]*=` -- unindented, no
`export ` prefix. Only those are definitions here. An `export KEY=` or an
indented `  KEY=` line is INERT: the loader skips it. `has` reports inert forms
separately (`inert=N`), and `set`/`unset` REFUSE while any inert form of the
key exists, because "which line did you mean" is a question for the operator.

WHAT IT GUARANTEES
------------------
* Exactly one key, spelled `^[A-Z][A-Z0-9_]*$`. Anything else is refused.
* It never prints, logs or audits a VALUE. Output is key, action, whether a
  line existed, and the old/new value LENGTH. A key that matches no line is
  printed as `<redacted: not present>` (it may be a value pasted by mistake).
* `set` reads the value from stdin (or a no-echo prompt when stdin is a TTY),
  never argv -- so the value is not in shell history or `ps`. The value is
  written VERBATIM and unquoted; with-env.sh sources values containing `${`
  raw, so the tool WARNS (without echoing) on `$(`, `${` or a backtick.
* Duplicates and inert forms are checked BEFORE the value is requested.
* The audit log is opened for append BEFORE any change; if it cannot be, the
  edit is refused. If the row still fails to land after the write, the tool
  prints `result=APPLIED-UNAUDITED` and exits 4 -- never "could-not-measure",
  which would read as "nothing happened".
* Before any change the file is copied to `<file>.bak-<UTC ts>`, mode 0600.
  Backups do not expire; see .claude/PATTERNS.md for cleanup.
* A symlinked path is resolved and written THROUGH: backup, temp file and
  rename all happen in the target's directory, and the resolved path is
  printed. A dangling link is refused.
* The write is atomic (temp `<name>.tmp-*` in the same directory, fsync,
  rename); mode is preserved (0600 for a file this tool creates) and owner is
  preserved when the process may set it.
* Every other line is preserved byte-for-byte (lines split on `\\n` only).
* An identical `set` is a no-op: `changed=no`, no backup, no audit row.

EXIT CODES
----------
  0  done / noop (for `has`: the key is defined exactly once)
  1  refused (malformed key, duplicate, inert form, empty or multi-line value,
     audit log not writable) -- or, for `has`, the key is not defined
  2  usage error
  3  could not measure; NOTHING was changed (file missing, unreadable, value
     not UTF-8)
  4  APPLIED-UNAUDITED: the edit landed but its audit row did not

`make` collapses every nonzero recipe exit to 2; read the printed `result=`
line, not make's exit code.

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

REDACTED = "<redacted: not present>"
# Per-invocation: has the edit landed, and has its audit row? Reset by main().
_STATE: dict[str, object] = {"applied": None, "backup": None, "audited": False}
RISKY_VALUE = ("$(", "${", "`")

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_UNMEASURABLE = 3
EXIT_APPLIED_UNAUDITED = 4


class Refused(Exception):
    """The request must not be applied. Nothing was changed."""

    def __init__(self, msg: str, show_key: bool = False):
        super().__init__(msg)
        self.show_key = show_key


class Unmeasurable(Exception):
    """No verdict can be given. Nothing was changed."""


# ------------------------------------------------------------------ parsing ---

def _split(data: bytes) -> list[bytes]:
    """Split on b"\\n" only, keeping ends. bytes.splitlines() would also split
    on \\v \\f \\x1c-\\x1e \\x85 and so act on a fragment of a line."""
    parts = data.split(b"\n")
    lines = [p + b"\n" for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _def_re(key: str) -> "re.Pattern[bytes]":
    # with-env.sh: `^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=` -- unindented only.
    return re.compile(rb"^" + re.escape(key.encode()) + rb"[ \t]*=")


def _inert_re(key: str) -> "re.Pattern[bytes]":
    # Shapes an operator would call "the line" but the loader never loads.
    k = re.escape(key.encode())
    return re.compile(rb"^(?:[ \t]+(?:export[ \t]+)?|export[ \t]+)" + k + rb"[ \t]*=")


def _scan(lines: list[bytes], key: str) -> tuple[list[int], list[int]]:
    d, i = _def_re(key), _inert_re(key)
    return ([n for n, ln in enumerate(lines) if d.match(ln)],
            [n for n, ln in enumerate(lines) if i.match(ln)])


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


# ------------------------------------------------------------------ file io ---

def _utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_target(path: Path) -> tuple[Path, Path | None]:
    """Return (path to act on, link path or None). Refuse a dangling link."""
    if path.is_symlink():
        target = Path(os.path.realpath(path))
        if not target.exists():
            raise Refused("dangling symlink; nothing to write through to")
        return target, path
    return path, None


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:  # permission, is-a-directory, ...
        raise Unmeasurable(f"cannot read file: {exc.__class__.__name__}") from exc


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


def _warn_lost_owner(owner: tuple[int, int]) -> None:
    """fchown was not permitted: the replaced file takes this process's
    uid/gid. Say which group was lost (names only, never a value)."""
    uid, gid = owner
    if gid == os.getegid() and uid == os.geteuid():
        return  # nothing lost
    try:
        import grp
        group = grp.getgrgid(gid).gr_name
    except (ImportError, KeyError):
        group = str(gid)
    print(f"env-local-key: WARNING: could not preserve owner/group (uid={uid} "
          f"group={group}); the file is now owned by uid={os.geteuid()} "
          f"gid={os.getegid()}. Re-apply with chgrp if another account reads it.",
          file=sys.stderr)


def _atomic_write(path: Path, data: bytes, mode: int,
                  owner: tuple[int, int] | None) -> None:
    # `<name>.tmp-*` so the leftover of a crash still matches the `.env.*`
    # ignore rule (a leading-dot prefix made it `..env.local.tmp-*`).
    fd, tmp = tempfile.mkstemp(prefix=f"{path.name}.tmp-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        if owner is not None:
            try:
                os.fchown(fd, *owner)
            except PermissionError:
                _warn_lost_owner(owner)
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


class _AuditLog:
    """Opened BEFORE the edit, so an unwritable log refuses the edit."""

    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        except OSError as exc:
            raise Refused(f"audit log not writable ({exc.__class__.__name__}); "
                          "nothing changed") from exc
        try:  # re-tighten a pre-existing looser file
            os.fchmod(self.fd, 0o600)
        except OSError:
            pass

    def append(self, row: dict[str, object]) -> None:
        fd = self.fd
        if fd is None:
            raise OSError("audit log already closed")
        try:
            os.write(fd, (json.dumps(row, sort_keys=True) + "\n").encode())
            os.fsync(fd)
        finally:
            self.close()

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            finally:
                self.fd = None


# ------------------------------------------------------------------- output ---

def _report(**fields: object) -> None:
    order = ["result", "key", "action", "line_existed", "count", "inert",
             "old_len", "new_len", "changed", "backup", "file", "via", "audit"]
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
        raise Refused("empty value refused; use unset to remove a key", show_key=True)
    if "\n" in text or "\r" in text:
        raise Refused("multi-line value refused", show_key=True)
    if any(tok in text for tok in RISKY_VALUE):
        print("env-local-key: WARNING: the value contains `$(`, `${` or a backtick; "
              "with-env.sh sources such values raw, so they are expanded or executed "
              "at load time. Written as given.", file=sys.stderr)
    return text.encode("utf-8")


def _row(key: str, action: str, **extra: object) -> dict[str, object]:
    # Explicitly dict[str, object]: the literal below is all-str, so a checker
    # infers dict[str, str] and flags the update with int/None/bool lengths.
    row: dict[str, object] = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "key": key,
        "action": action,
        "operator": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
    }
    row.update(extra)
    return row


def _refuse_ambiguous(key: str, defs: list[int], inert: list[int]) -> None:
    if len(defs) > 1:
        raise Refused(f"{key} is defined {len(defs)} times; resolve by hand-review, "
                      "not by guess", show_key=True)
    if inert:
        raise Refused(f"{key} has {len(inert)} inert form(s) (export-prefixed or "
                      "indented; with-env.sh does not load them); resolve by hand "
                      "before using this road", show_key=True)


def _commit(target: Path, via: Path | None, new: bytes, data: bytes | None,
            audit: _AuditLog, row: dict[str, object], report: dict[str, object]) -> int:
    """Backup, atomic write, audit. The audit log is already open."""
    try:
        if data is None:
            mode, owner, bak_name = 0o600, None, None
        else:
            st = target.stat()
            mode, owner = stat.S_IMODE(st.st_mode), (st.st_uid, st.st_gid)
            bak_name = _backup(target, data).name
        _atomic_write(target, new, mode, owner)
    except BaseException:
        audit.close()  # the file is unchanged: os.replace never ran
        raise
    # From here on the edit HAS landed; main's fallback handler reads this so
    # a later failure (e.g. a broken stdout pipe in _report) is never
    # reported as "nothing changed".
    _STATE.update(applied=str(target), backup=bak_name, audited=False)
    row["backup"] = bak_name
    report.update(backup=bak_name, file=target, via=via, audit=audit.path)
    try:
        audit.append(row)
        _STATE["audited"] = True
    except OSError as exc:
        report["result"] = "APPLIED-UNAUDITED"
        _report(**report)
        print(f"env-local-key: !!! APPLIED-UNAUDITED: the edit to {target} LANDED "
              f"(backup={bak_name}) but its audit row did NOT "
              f"({exc.__class__.__name__}). Record it by hand.", file=sys.stderr)
        return EXIT_APPLIED_UNAUDITED
    report["result"] = "done"
    _report(**report)
    return EXIT_OK


# ----------------------------------------------------------------- commands ---

def cmd_has(path: Path, key: str) -> int:
    target, via = _resolve_target(path)
    data = _read(target)
    if data is None:
        raise Unmeasurable("file does not exist")
    lines = _split(data)
    defs, inert = _scan(lines, key)
    if len(defs) > 1:
        raise Refused(f"{key} is defined {len(defs)} times", show_key=True)
    present = len(defs) == 1
    shown = key if (present or inert) else REDACTED
    _report(result="present" if present else "absent", key=shown, action="has",
            line_existed=present, count=len(defs), inert=len(inert),
            old_len=_value_len(lines[defs[0]]) if present else None,
            file=target, via=via)
    return EXIT_OK if present else EXIT_REFUSED


def cmd_unset(path: Path, key: str, audit_path: Path) -> int:
    target, via = _resolve_target(path)
    data = _read(target)
    if data is None:
        raise Unmeasurable("file does not exist")
    lines = _split(data)
    defs, inert = _scan(lines, key)
    _refuse_ambiguous(key, defs, inert)
    if not defs:
        # No audit row and no key echo: nothing happened, and the text may be
        # a value pasted into KEY= by mistake.
        _report(result="noop", key=REDACTED, action="unset", line_existed=False,
                changed=False, file=target, via=via)
        return EXIT_OK
    i = defs[0]
    old_len = _value_len(lines[i])
    audit = _AuditLog(audit_path)
    new = b"".join(lines[:i] + lines[i + 1:])
    return _commit(target, via, new, data, audit,
                   _row(key, "unset", old_len=old_len, new_len=None,
                        line_existed=True, changed=True),
                   dict(key=key, action="unset", line_existed=True,
                        old_len=old_len, new_len=None, changed=True))


def cmd_set(path: Path, key: str, audit_path: Path, stdin) -> int:
    target, via = _resolve_target(path)
    data = _read(target)
    lines = _split(data) if data is not None else []
    defs, inert = _scan(lines, key)
    _refuse_ambiguous(key, defs, inert)        # BEFORE asking for the value
    value = _read_value(stdin, key)
    body = key.encode() + b"=" + value
    existed = bool(defs)
    old_len = _value_len(lines[defs[0]]) if existed else None
    if data is None:
        new = body + b"\n"
    elif existed:
        i = defs[0]
        lines[i] = body + _eol(lines[i])
        new = b"".join(lines)
    else:
        sep = b"" if (not data or data.endswith(b"\n")) else b"\n"
        new = data + sep + body + b"\n"
    new_len = len(value.decode("utf-8"))
    if data is not None and new == data:
        _report(result="noop", key=key, action="set", line_existed=True,
                old_len=old_len, new_len=new_len, changed=False, file=target, via=via)
        return EXIT_OK
    audit = _AuditLog(audit_path)
    return _commit(target, via, new, data, audit,
                   _row(key, "set", old_len=old_len, new_len=new_len,
                        line_existed=existed, changed=True),
                   dict(key=key, action="set", line_existed=existed,
                        old_len=old_len, new_len=new_len, changed=True))


# --------------------------------------------------------------------- main ---

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


def _is_default_file(path: Path) -> bool:
    # String comparison of the GIVEN path first: no filesystem access at all.
    if os.path.abspath(path) == str(DEFAULT_FILE):
        return True
    return os.path.realpath(path) == os.path.realpath(DEFAULT_FILE)


def _report_applied(action: str, exc: BaseException) -> int:
    """The fallback path AFTER the write: say APPLIED, never "nothing changed".
    stderr first -- stdout may be the thing that just broke."""
    line = (f"env-local-key: result=APPLIED action={action} file={_STATE['applied']} "
            f"backup={_STATE['backup']} audited={'yes' if _STATE['audited'] else 'NO'} "
            f"error={exc.__class__.__name__}: the edit LANDED; only the reporting failed")
    try:
        print(line, file=sys.stderr)
    except OSError:
        pass
    return EXIT_APPLIED_UNAUDITED


def main(argv: list[str] | None = None, stdin=None) -> int:
    _STATE.update(applied=None, backup=None, audited=False)
    args = build_parser().parse_args(argv)
    stdin = stdin if stdin is not None else sys.stdin
    key = args.key
    if not KEY_RE.match(key):
        # Do not echo the rejected text: it may be a value pasted by mistake.
        print(f"env-local-key: result=refused action={args.cmd} "
              f"reason=malformed-key key_len={len(key)} (need ^[A-Z][A-Z0-9_]*$)",
              file=sys.stderr)
        return EXIT_REFUSED
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_default_file(args.file):
        print("env-local-key: result=refused reason=the default node-local overlay "
              "is off limits under pytest; pass --file <temp file>", file=sys.stderr)
        return EXIT_REFUSED
    try:
        if args.cmd == "has":
            return cmd_has(args.file, key)
        if args.cmd == "unset":
            return cmd_unset(args.file, key, args.audit_log)
        return cmd_set(args.file, key, args.audit_log, stdin)
    except Refused as exc:
        print(f"env-local-key: result=refused key={key if exc.show_key else REDACTED} "
              f"action={args.cmd} reason={exc}", file=sys.stderr)
        return EXIT_REFUSED
    except UnicodeDecodeError:
        print(f"env-local-key: result=could-not-measure action={args.cmd} "
              "reason=the value on stdin is not valid UTF-8; nothing changed",
              file=sys.stderr)
        return EXIT_UNMEASURABLE
    except Unmeasurable as exc:
        print(f"env-local-key: result=could-not-measure key={REDACTED} action={args.cmd} "
              f"reason={exc}; nothing changed", file=sys.stderr)
        return EXIT_UNMEASURABLE
    except OSError as exc:
        if _STATE["applied"]:
            return _report_applied(args.cmd, exc)
        print(f"env-local-key: result=could-not-measure key={REDACTED} action={args.cmd} "
              f"reason={exc.__class__.__name__}; nothing changed", file=sys.stderr)
        return EXIT_UNMEASURABLE


if __name__ == "__main__":
    sys.exit(main())
