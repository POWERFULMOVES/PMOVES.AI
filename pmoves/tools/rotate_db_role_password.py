#!/usr/bin/env python3
"""rotate_db_role_password.py - rotate a Postgres role's password without the
plaintext ever reaching argv, shell history, the wire, or the server log.

WHY THIS EXISTS
---------------
`JUICEFS_META_CREDENTIAL_RUNBOOK.md` §2.2-alt says, in as many words:

    "This belongs behind a Make target that reads from stdin, alongside
     secrets-rotate. Until that exists, use the form above."

This is that target's implementation. It also goes one step further than the
runbook's interim form, for a reason PostgreSQL documents itself.

WHAT THE RUNBOOK'S INTERIM FORM DOES AND DOES NOT SOLVE
The runbook pipes `ALTER ROLE x PASSWORD '<plaintext>'` on stdin instead of
using `psql -c` or `-v`. That correctly keeps the value out of **argv** and out
of **shell history**. It does not address the rest of the exposure. From the
official ALTER ROLE page:

    "Caution must be exercised when specifying an unencrypted password with
     this command. The password will be transmitted to the server in cleartext,
     and it might also be logged in the client's command history or the server
     log."
    -- https://www.postgresql.org/docs/17/sql-alterrole.html

So with the interim form the secret still crosses the socket in the clear and
can land in the server log whenever `log_statement` is `ddl` or `all`.

WHAT POSTGRES RECOMMENDS INSTEAD
psql's own `\\password` meta-command exists precisely for this:

    "This command prompts for the new password, encrypts it, and sends it to
     the server as an ALTER ROLE command. This makes sure that the new password
     does not appear in cleartext in the command history, the server log, or
     elsewhere."
    -- https://www.postgresql.org/docs/17/app-psql.html

`\\password` is interactive, so it cannot be scripted. But the property that
makes it safe - encrypting CLIENT-SIDE - is available to any client, because:

    "If the presented password string is already in MD5-encrypted or
     SCRAM-encrypted format, then it is stored as-is regardless of
     password_encryption (since the system cannot decrypt the specified
     encrypted password string, to encrypt it in a different format)."
    -- https://www.postgresql.org/docs/17/sql-createrole.html

So this tool computes the SCRAM-SHA-256 verifier locally and sends THAT. The
plaintext never leaves this process. What crosses the socket is already a hash,
and a server log capturing the statement captures only the verifier - which is
what `pg_authid` stores anyway.

SCRAM-SHA-256 verifier format (RFC 5802 / RFC 7677, as stored by PostgreSQL):

    SCRAM-SHA-256$<iterations>:<b64 salt>$<b64 StoredKey>:<b64 ServerKey>

    SaltedPassword = PBKDF2-HMAC-SHA256(password, salt, iterations)
    ClientKey      = HMAC(SaltedPassword, "Client Key")
    StoredKey      = SHA256(ClientKey)
    ServerKey      = HMAC(SaltedPassword, "Server Key")

ONE CONSTRAINT WORTH NAMING
RFC 5802 requires the password be SASLprep'd (RFC 4013) before hashing. SASLprep
is the identity function for printable ASCII, and this tool mints URL-safe
base64, which is printable ASCII. So SASLprep is a no-op HERE. It would NOT be a
no-op for an operator-supplied password containing non-ASCII, which is why this
tool mints rather than accepts one.

EXIT CODES
  0  rotated
  1  refused, or the ALTER failed
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import secrets
import subprocess
import sys

ITERATIONS = 4096  # PostgreSQL's default for password_encryption = scram-sha-256
SALT_BYTES = 16


def scram_sha256_verifier(password: str, salt: bytes, iterations: int = ITERATIONS) -> str:
    """Build the verifier string PostgreSQL stores in pg_authid.rolpassword."""
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    return "SCRAM-SHA-256${}:{}${}:{}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(stored_key).decode("ascii"),
        base64.b64encode(server_key).decode("ascii"),
    )


def mint(length: int) -> str:
    """URL-safe, printable ASCII - so SASLprep is a no-op (see module docstring)."""
    return secrets.token_urlsafe(length)[:length]


def quote_literal(s: str) -> str:
    """The verifier is base64 + '$' + ':' only, but never build SQL by trusting
    that. Double any single quote, the standard SQL escape."""
    return "'" + s.replace("'", "''") + "'"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", required=True, help="Postgres role to rotate")
    ap.add_argument("--container", default="pmoves-supabase-db-1",
                    help="container running psql (default: %(default)s)")
    ap.add_argument("--db", default="postgres")
    ap.add_argument("--admin-user", default="supabase_admin")
    ap.add_argument("--length", type=int, default=64)
    ap.add_argument("--emit-to-env", metavar="VAR",
                    help="write the new plaintext to this env var name on stdout as "
                         "VAR=value, for a caller that captures it. Omit to keep the "
                         "plaintext inside this process entirely.")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and report shape only; do not touch the database")
    a = ap.parse_args()

    if not a.role.replace("_", "").isalnum():
        sys.stderr.write("refusing: role name must be alphanumeric/underscore\n")
        return 1

    password = mint(a.length)
    verifier = scram_sha256_verifier(password, secrets.token_bytes(SALT_BYTES))
    stmt = "ALTER ROLE {} PASSWORD {};".format(a.role, quote_literal(verifier))

    if a.dry_run:
        # Never print the password or the verifier. Shape only.
        print("dry-run: would ALTER ROLE {} with a SCRAM-SHA-256 verifier "
              "({} iterations, {}-byte salt); plaintext length {}".format(
                  a.role, ITERATIONS, SALT_BYTES, a.length))
        return 0

    # The statement carries the VERIFIER, not the password. It still goes on
    # stdin rather than argv: argv is world-readable via /proc on Linux, and a
    # verifier is not a secret worth leaking either.
    proc = subprocess.run(
        ["docker", "exec", "-i", a.container,
         "psql", "-h", "127.0.0.1", "-U", a.admin_user, "-d", a.db,
         "-v", "ON_ERROR_STOP=1", "-q"],
        input=stmt, text=True, capture_output=True, timeout=60,
    )
    if proc.returncode != 0:
        sys.stderr.write("ALTER ROLE failed:\n{}\n".format(proc.stderr.strip()[:800]))
        return 1

    print("rotated {}: server now holds a client-computed SCRAM-SHA-256 verifier; "
          "the plaintext never crossed the socket".format(a.role))
    if a.emit_to_env:
        # Deliberately the ONLY path by which the plaintext leaves this process.
        # The caller is expected to consume this on a pipe, not echo it.
        print("{}={}".format(a.emit_to_env, password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
