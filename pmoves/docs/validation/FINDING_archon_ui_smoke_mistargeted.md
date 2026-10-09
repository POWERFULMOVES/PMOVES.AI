# Finding — `archon-ui-smoke` probes the wrong container, then passes anyway

Measured on B850 / Knuckles, 2026-09-08. Severity: the probe's name asserts more
than the probe measures.

## The target

`pmoves/Makefile:3926-3931`:

```make
archon-ui-smoke: ## Verify consolidated Archon service API/UI endpoints are reachable (200)
	@api=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); \
	 ui=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3737 || true); \
	...
```

## What each half actually measures

Archon's compose stanza declares **three** host publishes, all onto container port 3090:

```
127.0.0.1:3090 -> 3090
127.0.0.1:3737 -> 3090
127.0.0.1:8091 -> 3090
```

But the running container publishes only **two**:

```
$ docker port pmoves-archon-1
3090/tcp -> 127.0.0.1:3090
3090/tcp -> 127.0.0.1:3737          # 8091 is ABSENT
```

Because `pmoves-mcp-gateway` already holds `0.0.0.0:8091`:

```
$ docker ps --format '{{.Names}}\t{{.Ports}}' | grep 8091
pmoves-mcp-gateway    0.0.0.0:8091->8091/tcp
```

So:

| Half of the probe | Reaches | Result | Verdict |
|---|---|---|---|
| `:8091/healthz` — labelled "archon API" | **`pmoves-mcp-gateway`**, a different service | `401 Unauthorized` | Fails — but for a reason that has nothing to do with Archon |
| `:3737` — labelled "archon UI" | Archon (3737→3090) | `200` | **Passes, while Archon is completely non-functional** |

Contrast, same instant, same service:

```
:3090/healthz   -> 503   (archon, correctly reporting degraded)
:8091/healthz   -> 401   (mcp-gateway, unrelated)
:3737/          -> 200   (archon root — a liveness switch)
```

## Why this matters to the thesis

This is the failure mode *underneath* the switch-vs-shape distinction. A probe can be:

1. a switch (proves liveness only) — `:3737 -> 200` is this, and it goes green on a
   dead service;
2. **mis-targeted** — `:8091` is this, measuring a service other than the one it names.

Mis-targeting is worse than a switch, because it produces a *confident* verdict about
a service it never contacted. Here the two errors happened to cancel: the probe fails
overall, so nobody noticed that neither half establishes what its label claims.

**A red light for the wrong reason is not evidence.** When the 8091 collision is
eventually fixed, this probe will go green on the mcp-gateway's healthy response and
report Archon's API as validated.

## Recommended fix

1. Point the API half at a port Archon actually publishes (`:3090`), not `:8091`.
2. Assert on the readiness field, not the status code — `:3737` returning 200 is the
   switch this whole document argues against.
3. Separately: resolve the `:8091` collision between `archon` and `mcp-gateway`, or
   drop the unused third publish from Archon's compose stanza. Two services declaring
   the same host port is a latent trap regardless of this probe.

Items 1-2 are Makefile changes (writable). Item 3 is a compose change and is
**read-only on this node** — diff + operator action.

## Positive controls

- `:3737` reaching Archon and not something else: `docker ps` shows
  `pmoves-archon-1 ... 127.0.0.1:3737->3090/tcp`, and no other container publishes 3737.
- `:8091` reaching mcp-gateway and not Archon: `docker port pmoves-archon-1` does not
  list 8091 at all, and `docker ps` attributes `0.0.0.0:8091` to `pmoves-mcp-gateway`.
- The 503/401 split is not a transient: measured from the host on both ports and from
  inside the container, same instant, three consistent codes.
