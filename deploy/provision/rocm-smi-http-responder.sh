#!/bin/sh
# rocm-smi-http-responder.sh — per-connection HTTP responder for rocm-smi-http.socket
#
# WHY A SCRIPT AND NOT AN INLINE ExecStart:
# The previous unit inlined `/bin/sh -c 'printf "...Content-Length: %d..." "${#body}"'`
# directly in ExecStart. systemd expands BOTH `%` specifiers and `${VAR}` references in
# ExecStart before handing the string to the shell, so:
#   %d          -> /run/credentials/rocm-smi-http@N.service   (credentials-dir specifier)
#   %s          -> the user's shell                            (shell specifier)
#   ${#body}    -> ""  + journal warning "Invalid environment variable name ... #body"
# The printf format was corrupted and the length argument vanished, so every scrape got
# HTTP 200 with a zero-byte body — Prometheus scraped nothing while the port stayed bound
# and the socket unit looked healthy.
#
# Keeping the shell code in a real script means systemd never parses it. Escaping (%% and
# $$) would also work but is easy to reintroduce on the next edit.
#
# WHY wc -c AND cat, NOT "$(cat file)":
# Command substitution strips ALL trailing newlines, so Content-Length came out one byte
# short of the file (458 vs 459) and the exposition text lost its final newline — which
# the Prometheus text format requires. Taking the length from the file and streaming the
# file keeps the bytes on the wire identical to the bytes on disk.
set -eu

METRICS_FILE=/run/rocm-smi-metrics.prom

if [ -r "$METRICS_FILE" ]; then
    len=$(wc -c < "$METRICS_FILE")
else
    len=0
fi

printf 'HTTP/1.1 200 OK\r\n'
printf 'Content-Type: text/plain; version=0.0.4\r\n'
printf 'Content-Length: %d\r\n' "$len"
printf 'Connection: close\r\n'
printf '\r\n'

[ "$len" -gt 0 ] && cat "$METRICS_FILE"

exit 0
