#!/bin/sh
# Create the usr bind source of a standalone A0 fork (SPARK, DARKXSIDE) as the
# HOST user before `up`. Their compose files are named *-sidecar.yml, but each is
# a full A0 with local-node access, not a k8s-style sidecar.
#
# The /a0/usr mounts use `create_host_path: false`, so a missing source makes
# `up` fail at create instead of Docker silently creating an empty root-owned
# dir. SPARK and DARKXSIDE default to ./usr, which is gitignored and nothing else
# creates, so their roads create it here first; agent-zero-<name>-usr-init then
# hands it to 65532. The main agent-zero road does not use this: its
# data/agent-zero/usr carries tracked files and always exists in a clone.
#
# The source is resolved by compose itself (`config`), so it honours the same
# variable expression, env files and shell env that `up` will use. Run it
# inside the same with-env.sh shell as the `up` that follows.
#
# Usage: a0_usr_source_ensure.sh <project> <compose-file> <env-file> <service>
set -eu

if [ "$#" -ne 4 ]; then
	echo "usage: $0 <project> <compose-file> <env-file> <service>" >&2
	exit 2
fi
project=$1 file=$2 envfile=$3 service=$4

if [ "$(id -u)" = 0 ]; then
	echo "a0-usr-source: refusing to create the usr source as root; run the make target as the host user" >&2
	exit 1
fi

# Capture first: piping straight into python would hide compose's exit status
# and bury its error under a JSONDecodeError traceback.
if ! cfg=$(docker compose -p "$project" -f "$file" --env-file "$envfile" config --format json); then
	echo "a0-usr-source: docker compose config failed for $project (error above); not creating anything" >&2
	exit 1
fi

src=$(printf '%s' "$cfg" | python3 -c '
import json, sys
try:
    svc = json.load(sys.stdin)["services"][sys.argv[1]]
except (ValueError, KeyError) as exc:
    sys.exit("a0-usr-source: cannot read service %s from compose config: %s" % (sys.argv[1], exc))
found = [v["source"] for v in svc.get("volumes") or [] if v.get("target") == "/a0/usr"]
if len(found) != 1:
    sys.exit("a0-usr-source: expected one /a0/usr mount on %s, found %d" % (sys.argv[1], len(found)))
print(found[0])
' "$service")

if [ -d "$src" ]; then
	echo "a0-usr-source: $src exists"
else
	mkdir -p "$src"
	echo "a0-usr-source: created $src as $(id -un) (agent-zero usr-init hands it to 65532)"
fi
