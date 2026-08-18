#!/bin/sh
# rocm-smi-http-responder.sh — per-connection HTTP responder for rocm-smi-http.socket
#
# WHY A SCRIPT AND NOT AN INLINE ExecStart:
# The unit used to inline `/bin/sh -c 'printf "...Content-Length: %d..." "${#body}"'`
# directly in ExecStart. systemd expands BOTH `%` specifiers and `${VAR}` references
# in ExecStart before handing the string to the shell, so:
#   %d          -> /run/credentials/rocm-smi-http@N.service   (credentials-dir specifier)
#   %s          -> the user's shell                            (shell specifier)
#   ${#body}    -> ""  + journal warning "Invalid environment variable name ... #body"
# The printf format was corrupted and the length argument vanished, so every scrape
# got HTTP 200 with a zero-byte body — while the socket unit reported
# active(listening) and the metrics file on disk was perfectly valid.
#
# Keeping the shell code in a real script means systemd never parses it. Escaping
# (%% and $$) would also work but is easy to reintroduce on the next edit.
set -eu

METRICS_FILE=/run/rocm-smi-metrics.prom
# A scrape older than this means the collector loop is wedged or dead. The collector
# rewrites every 10s; 60s is six missed cycles.
STALE_AFTER_SECONDS=60

# Drain the request headers before replying. A socket closed with unread data sends
# RST, which can discard the response we just wrote — producing intermittent
# "connection reset by peer" scrapes that hand-testing never reproduces. Bounded by
# the blank line that ends the headers, and by read's own EOF.
while IFS= read -r _line; do
    case "$_line" in ''|"$(printf '\r')") break ;; esac
done 2>/dev/null || true

respond() {
    # $1 status line, $2 body
    _body="$2"
    printf 'HTTP/1.1 %s\r\n' "$1"
    printf 'Content-Type: text/plain; version=0.0.4\r\n'
    printf 'Content-Length: %d\r\n' "${#_body}"
    printf 'Connection: close\r\n'
    printf '\r\n'
    printf '%s' "$_body"
    exit 0
}

# Missing/unreadable file is a REAL failure, not an empty success. Returning 200 with
# zero bytes is what made the original bug invisible: Prometheus records up=1 and the
# panel just goes blank. 503 makes the target go down and alert.
[ -r "$METRICS_FILE" ] || respond '503 Service Unavailable' \
    "# rocm-smi exporter: $METRICS_FILE missing or unreadable"

# Read the file ONCE into memory. The collector writes to a temp file and mv's it into
# place every 10s; taking the length with `wc -c` and then `cat`ing the same path is
# two separate opens that can straddle that rename, sending a Content-Length that
# disagrees with the bytes actually written (truncated parse error, or a client
# hanging on a short read).
body="$(cat "$METRICS_FILE")" || respond '503 Service Unavailable' \
    "# rocm-smi exporter: failed to read $METRICS_FILE"

# `$(...)` strips trailing newlines; the Prometheus text format requires a final one.
# Re-add exactly one so wire bytes match what the collector intended.
body="$body
"

# A stale file is also a failure: without this the responder would happily serve the
# last good scrape forever after the collector died — metrics frozen, everything green.
now="$(date +%s)"
mtime="$(stat -c %Y "$METRICS_FILE" 2>/dev/null || echo 0)"
age=$((now - mtime))
if [ "$mtime" -gt 0 ] && [ "$age" -gt "$STALE_AFTER_SECONDS" ]; then
    respond '503 Service Unavailable' \
        "# rocm-smi exporter: metrics are ${age}s old (>${STALE_AFTER_SECONDS}s); collector is not running"
fi

respond '200 OK' "$body"
