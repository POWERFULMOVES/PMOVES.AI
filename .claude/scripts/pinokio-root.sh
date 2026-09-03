#!/usr/bin/env bash
# pinokio-root.sh — print the Pinokio install root for THIS node. Nothing else.
#
# WHY A WHOLE FILE FOR ONE PATH
# -----------------------------
# Because the path was already hardcoded as `D:\pinokio` in nine places, and on
# this node every one of them is wrong:
#   .claude/commands/pinokio/{app-list,app-search,app-start,app-stop,voice-apps}.md
#   .claude/settings.json  (directory allowlist)
#   .claude/PATTERNS.md, CLAUDE.md, .claude/PINOKIO_LAUNCHER_GUIDE.md (18 refs)
#
# Measured on the 4090, 2026-09-02: `D:/pinokio` does not exist; the install is
# at `C:/pinokio`, and `C:/pinokio/bin/npm/pterm.cmd` is present. Every
# `pinokio:*` command therefore failed at its first call with a bare
# FileNotFoundError from subprocess, which reads as "Pinokio is broken" rather
# than "the path is wrong on this node".
#
# THE FIX IS NOT `C:` . A drive letter is a PER-NODE value, and D: is very
# likely correct on the 5090 or Z890 -- swapping the literal just moves which
# nodes are broken. This is the same defect as `curl localhost:4222/healthz`
# (a port that varies), `qwen3-embedding:4b` (a model one node had pulled), and
# a rotation default masquerading as a spec: a per-node value written down as a
# fleet constant, which survives review everywhere except the node it breaks.
#
# Same contract as its sibling .claude/scripts/nats-endpoint.sh: ask the node.
#
# Usage:  PINOKIO_ROOT=$(bash .claude/scripts/pinokio-root.sh) || true
#         "$PINOKIO_ROOT/bin/npm/pterm.cmd" search ''
#
# Exit 0 + root on stdout when a real install was FOUND (pterm present).
# Exit 1 + the best guess on stdout when nothing was found, so a caller that
# ignores the status still gets a usable path rather than an empty string --
# but a caller that checks it can say "assumed" instead of reporting a
# measurement it never made.
set -uo pipefail

# Explicit override always wins: a node with a non-standard install says so
# once, here, rather than editing every consumer.
CANDIDATES=()
[ -n "${PINOKIO_ROOT:-}" ] && CANDIDATES+=("$PINOKIO_ROOT")
CANDIDATES+=(
  "C:/pinokio"
  "D:/pinokio"
  "$HOME/pinokio"
  "/c/pinokio"
  "/d/pinokio"
)

# pterm is the thing every consumer actually invokes, so its presence -- not the
# directory's -- is what makes a root usable. `C:/Users/<user>/pinokio` exists on
# this node and contains only `logs/`, which a directory-existence check would
# have accepted and then failed on at the first call.
for root in "${CANDIDATES[@]}"; do
  [ -z "$root" ] && continue
  for exe in "$root/bin/npm/pterm.cmd" "$root/bin/npm/pterm"; do
    if [ -f "$exe" ]; then
      printf '%s\n' "$root"
      exit 0
    fi
  done
done

# Nothing usable. Emit the historical default so an unguarded caller behaves as
# it did before, and signal the difference through the exit status.
printf '%s\n' "D:/pinokio"
exit 1
