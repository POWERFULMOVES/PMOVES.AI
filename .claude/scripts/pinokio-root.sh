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
# Usage:  PTERM=$(bash .claude/scripts/pinokio-root.sh --exe) || true
#         "$PTERM" search ''
#
#         PINOKIO_ROOT=$(bash .claude/scripts/pinokio-root.sh) || true   # docs/paths
#
# Anything that INVOKES pterm must use --exe: it returns the executable this
# script actually stat'd, so the path you run is the path that was validated.
# Appending /bin/npm/pterm.cmd to the bare root re-creates the bug --exe exists
# to close (a node with only the extensionless `pterm` passes validation and
# then fails at the call).
#
# Exit 0 + root on stdout when a real install was FOUND (pterm present).
# Exit 1 + the best guess on stdout when nothing was found, so a caller that
# ignores the status still gets a usable path rather than an empty string --
# but a caller that checks it can say "assumed" instead of reporting a
# measurement it never made.
set -uo pipefail

# --exe prints the validated pterm executable; bare prints its root. Consumers
# that invoke pterm MUST use --exe, so the path they run is the path this script
# tested. Docs that reference other files under the install (prototype/PINOKIO.md,
# prototype/system/examples) want the bare root.
WANT_EXE=0
case "${1:-}" in
  --exe) WANT_EXE=1 ;;
  "") : ;;
  *) printf 'usage: pinokio-root.sh [--exe]\n' >&2; exit 2 ;;
esac

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
#
# EMIT WHAT WAS VALIDATED. `--exe` prints the executable that actually passed the
# -f test; bare invocation prints its root. The first version validated EITHER
# `pterm.cmd` OR `pterm` and then returned only the root, while every consumer
# appended `/bin/npm/pterm.cmd` -- so on a node carrying only the extensionless
# `pterm` (any Linux/macOS node) this reported success and every caller built a
# path to a file that does not exist. Review P2 on PR #2891.
#
# That is the same defect as crush_configurator.py before PR #2887: candidates
# were checked against repo_root and emitted relative, so the path validated was
# not the path used. Worth naming twice, because it is easy to write again --
# the check and the emit drift apart when they are two separate expressions.
for root in "${CANDIDATES[@]}"; do
  [ -z "$root" ] && continue
  for exe in "$root/bin/npm/pterm.cmd" "$root/bin/npm/pterm"; do
    if [ -f "$exe" ]; then
      if [ "$WANT_EXE" = "1" ]; then
        printf '%s\n' "$exe"
      else
        printf '%s\n' "$root"
      fi
      exit 0
    fi
  done
done

# Nothing usable. Emit the historical default so an unguarded caller behaves as
# it did before, and signal the difference through the exit status. --exe keeps
# the same contract: always a path of the shape the caller asked for, never an
# empty string, with the exit status carrying "this was assumed, not measured".
if [ "$WANT_EXE" = "1" ]; then
  printf '%s\n' "D:/pinokio/bin/npm/pterm.cmd"
else
  printf '%s\n' "D:/pinokio"
fi
exit 1
