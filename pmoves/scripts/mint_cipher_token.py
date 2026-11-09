#!/usr/bin/env python3
"""Mint a per-agent cipher token and insert it into Supabase cipher_agent_tokens."""

import argparse
import json
import os
import sys
import uuid

import urllib.request
import urllib.error

import importlib.util
from pathlib import Path


def _load_cipher_identity():
    """Import pmoves/tools/cipher_identity.py BY PATH, without touching sys.path.

    One card reader for this pipeline, not a second copy: cipher_identity reads
    the cards to report which agent a SESSION carries, this script reads them to
    decide which agent may be MINTED, and if the two ever disagree about what an
    active card is then the gate is theatre.

    The obvious way to share it -- `sys.path.insert(0, .../tools)` -- is a global
    side effect that outlives this import. `pmoves/tools/` holds several
    `test_*.py` helpers (test_bpm_encoder, test_chit_tools, test_hf_ssl, ...), so
    prepending that directory inside a pytest process can shadow real test
    modules by bare name. A CLI has no business rearranging the importer for
    whatever runs after it.
    """
    path = Path(__file__).resolve().parents[1] / "tools" / "cipher_identity.py"
    spec = importlib.util.spec_from_file_location("_pmoves_cipher_identity", path)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging guard
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ci = _load_cipher_identity()
CARDS = _ci.CARDS
load_active_card_agents = _ci.load_active_card_agents


def _redact(text: str, token_uuid: uuid.UUID) -> str:
    """Blank both spellings of the uuid: stored form is dashed, bearer form is not."""
    for form in (str(token_uuid), token_uuid.hex):
        text = text.replace(form, "<redacted:token_uuid>")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a per-agent cipher token")
    parser.add_argument("--agent", required=True, help="Agent identifier (e.g. crush-spark)")
    parser.add_argument("--scopes", default="memory:read,memory:write", help="Comma-separated scopes")
    parser.add_argument("--rest-url", default=os.environ.get("SUPABASE_REST_URL", "http://localhost:8000/rest/v1"))
    parser.add_argument("--service-key", default=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SERVICE_ROLE_KEY", "")))
    parser.add_argument(
        "--emit",
        choices=("fd", "file", "stdout"),
        default="stdout",
        help="where the minted bearer goes. stdout is the DEFAULT because "
             "TAC_CIPHER_VILLAGE.md:86 specifies it ('-> prints token') and the "
             "tests enforce that; fd (caller-opened) and file (0600) are the "
             "transcript-safe options. Flipping the default is a SPEC change and "
             "is proposed, not taken, in CIPHER_TOKEN_LANE_AUDIT_2026-09-17.md",
    )
    parser.add_argument(
        "--emit-fd", type=int, default=3,
        help="file descriptor for --emit=fd (default 3; open it in the caller)",
    )
    parser.add_argument(
        "--emit-file", default="",
        help="destination path for --emit=file (created 0600)",
    )
    parser.add_argument(
        "--allow-uncarded",
        action="store_true",
        help="mint for an agent that has no active signing card (records the exception loudly)",
    )
    args = parser.parse_args()

    if args.emit == "file" and not args.emit_file:
        parser.error("--emit=file requires --emit-file PATH")

    # The signing card is the unlock. #2935 recorded that "the signature and the
    # ledger are separate systems" as a finding; until this gate, it was also the
    # implementation -- `--agent` took any string, so the memory layer would file
    # rows under identities the CHIT pipeline had never heard of and could never
    # verify. A minted token is an authority to BE someone in fleet memory, and
    # authority comes from the card or it comes from nowhere.
    # Explicit CARDS, not the imported default: the module-level name is what a
    # test (or an operator with a staging roster) can redirect. Relying on the
    # default binding would make the gate untestable except against live cards.
    active_cards, card_err = load_active_card_agents(CARDS)
    if card_err:
        blocker = f"cannot verify a signing card for {args.agent!r}: {card_err}"
        remedy = "install PyYAML or restore the card file, or pass --allow-uncarded"
    elif args.agent not in active_cards:
        blocker = f"{args.agent!r} has no ACTIVE card in {CARDS}"
        remedy = "add a card (make -C pmoves keygen-cards) or pass --allow-uncarded"
    else:
        blocker = remedy = ""

    if blocker:
        if not args.allow_uncarded:
            print(f"error: {blocker}", file=sys.stderr)
            print(f"       {remedy}", file=sys.stderr)
            return 1
        # Proceeding is the operator's call, but it is never quiet. An uncarded
        # token is an identity fleet memory will accept and the signing pipeline
        # cannot verify -- exactly the split this gate exists to close.
        print(f"WARNING: {blocker}", file=sys.stderr)
        print(
            f"WARNING: minting UNCARDED token for {args.agent!r} -- this identity can write "
            "to fleet memory but cannot be verified by the CHIT signing pipeline",
            file=sys.stderr,
        )

    if not args.service_key:
        print("error: SUPABASE_SERVICE_KEY or SERVICE_ROLE_KEY must be set", file=sys.stderr)
        return 1

    token_uuid = uuid.uuid4()
    token = f"cipher_{token_uuid.hex}"
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]

    payload = {
        "token_uuid": str(token_uuid),
        "agent_id": args.agent,
        "scopes": scopes,
    }

    body = json.dumps(payload).encode("utf-8")
    url = f"{args.rest_url}/cipher_agent_tokens"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": args.service_key,
            "Authorization": f"Bearer {args.service_key}",
            "Content-Profile": "pmoves_core",
            "Prefer": "return=representation",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        # A duplicate-key or constraint error quotes the offending VALUE back,
        # and that value is token_uuid. Server-controlled text is not a safe
        # place to assume the credential is absent.
        print(
            f"error: Supabase returned {e.code}: {_redact(detail, token_uuid)}",
            file=sys.stderr,
        )
        return 1

    # The response body is deliberately NOT printed.
    #
    # The insert is sent with `Prefer: return=representation`, so Supabase echoes
    # the stored row -- and that row carries token_uuid, from which the bearer
    # `cipher_{token_uuid.hex}` is reconstructable in full. There is no hash
    # column (migration 20260728100000: `token_uuid UUID PRIMARY KEY`), so the
    # stored row IS the credential.
    #
    # Printing it put a SECOND copy on stdout wearing no label. An operator or
    # log scrubber redacting `CIPHER_TOKEN=` removed the copy they could see and
    # left the one they could not. Two emissions, one invisible to redaction, is
    # strictly worse than one: it makes the transcript look clean.
    #
    # The body is still parsed, because "accepted but stored nothing" has to be
    # an error rather than a token the operator will try to use.
    if raw.strip():
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            print("error: Supabase response was not JSON", file=sys.stderr)
            return 1
        if isinstance(rows, list) and not rows:
            print(
                "error: Supabase accepted the insert but returned no row; "
                "the token was NOT registered",
                file=sys.stderr,
            )
            return 1

    # HANDOFF, NOT STDOUT. The bearer used to be printed here, which is the
    # single reason this Known Road could not be run inside an agent transcript:
    # the credential lands in the log, and a log is exactly where a credential
    # stops being attributable to one agent.
    #
    # A signing card is a LIVING record of provenance -- checkable, current,
    # deterministically maintained. A secret that has been copied into a
    # transcript is no longer bound to the identity the card attests, so the
    # printing was not a hygiene nit; it broke the thing the card is for.
    #
    # The repo already had the convention and this adopts it rather than
    # inventing one: `make secrets-rotate` takes its value from
    # PMOVES_ROTATE_VALUE, and cf_dns_token_provision.py:194 passes secrets
    # "into the CHILD ENV as PMOVES_ROTATE_VALUE (never argv)". Env, never
    # argv, never stdout -- argv is world-readable in /proc on Linux and in
    # Get-CimInstance Win32_Process on Windows, so a value passed as a flag is
    # readable by any process on the box for as long as the command runs.
    #
    # --emit=fd is the safe default for automation: the caller opens the fd, so
    # the value never touches a filesystem path an onlooker could read later.
    # --emit=file writes 0600. --emit=stdout is retained and must be ASKED FOR,
    # because there are legitimate interactive uses and a flag the operator
    # typed is a different act from a tool that leaks by default.
    names_only = f"AGENT={args.agent}{chr(10)}SCOPES={','.join(scopes)}"

    if args.emit == "stdout":
        print(f"CIPHER_TOKEN={token}")
        print(names_only)
        return 0

    if args.emit == "fd":
        try:
            with os.fdopen(os.dup(args.emit_fd), "w", closefd=True) as fh:
                fh.write(token)
        except OSError as exc:
            print(
                f"error: could not write the token to fd {args.emit_fd}: {exc}. "
                "Open it in the caller (3>/path or a pipe) before invoking.",
                file=sys.stderr,
            )
            return 1
        print(names_only)
        print(f"TOKEN_WRITTEN_TO=fd:{args.emit_fd}")
        return 0

    # emit == file
    dest = Path(args.emit_file).expanduser()
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Create with 0600 from the start: writing then chmod'ing leaves a
        # window where the file is world-readable, which is the whole hazard.
        fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(token)
    except OSError as exc:
        print(f"error: could not write the token to {dest}: {exc}", file=sys.stderr)
        return 1
    print(names_only)
    print(f"TOKEN_WRITTEN_TO={dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
