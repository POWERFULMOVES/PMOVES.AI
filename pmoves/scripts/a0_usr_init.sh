#!/bin/sh
# Hand the Agent Zero user tree (/a0/usr) to the container's runtime uid.
#
# The A0 image runs as 65532 (services/agent-zero/Dockerfile, `USER pmoves`;
# docker-compose.hardened.yml pins `user: "65532:65532"` too). The host seeds
# the bind-mounted usr tree as its own uid (1000 on our nodes), and Docker
# does not change the ownership of a bind mount, so A0 hits EACCES on every
# plugin install and settings save while its healthcheck stays green.
#
# Runs as a one-shot compose service (agent-zero-usr-init) that agent-zero
# depends on with `condition: service_completed_successfully`, so compose starts
# it on every bring-up path that resolves dependencies. Recipes that pass
# --no-deps must run it explicitly (see up-a0-archon-scoped).
#
# Invariants:
#   - Ownership only, never chmod: no permission bit is ever added (the kernel's
#     chown can only clear set-id bits), so a 0600 credential under
#     plugins/_oauth stays 0600 and plugin code gains no write bit. Handing a
#     credential to 65532 narrows rather than broadens: A0 is the only process
#     that writes or reads those files (write_private_json and the codex helper
#     create them 0600 as 65532).
#   - Symlinks are never followed: find does not follow them and `chown -h`
#     changes the link, not its target. -xdev stays on the mounted filesystem.
#   - Fails loudly: a missing mount, a failed chown, or an entry still not owned
#     by the runtime uid afterwards exits nonzero, and agent-zero does not start.
set -eu

dir="${A0_USR_DIR:-/a0/usr}"
uid="${A0_USR_UID:-65532}"
gid="${A0_USR_GID:-65532}"

if [ -L "$dir" ] || [ ! -d "$dir" ]; then
	echo "a0-usr-init: $dir is not a directory; is the usr bind mount (AGENT_ZERO_USR_DIR) missing?" >&2
	exit 1
fi

find "$dir" -xdev \( ! -user "$uid" -o ! -group "$gid" \) -exec chown -h "$uid:$gid" {} +

left=$(find "$dir" -xdev \( ! -user "$uid" -o ! -group "$gid" \) -print)
if [ -n "$left" ]; then
	echo "a0-usr-init: entries under $dir are still not owned by $uid:$gid:" >&2
	printf '%s\n' "$left" >&2
	exit 1
fi

echo "a0-usr-init: $dir owned by $uid:$gid (no mode bits added)"
