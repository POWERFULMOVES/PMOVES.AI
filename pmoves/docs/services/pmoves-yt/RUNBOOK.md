# PMOVES.YT — Docker / Service Runbook

Operational runbook for the PMOVES.YT ingest chain: `pmoves-yt`, `ffmpeg-whisper`,
`bgutil-pot-provider`, and the `yt-cookie-writer` / `yt-cookie-refresher` pair.

**Scope.** Bring-up, health verification, the cookie chain, logs, failure triage, teardown.

**Not in scope.** *Which* yt-dlp version you should be on, and how current it is against upstream —
that is [`YTDLP_CURRENCY.md`](./YTDLP_CURRENCY.md) (PR #2793). This runbook tells you how to find out
what you are *actually* running; that doc tells you whether it is current. See also
[`README.md`](./README.md) and [`UPDATE_NOTES.md`](./UPDATE_NOTES.md).

> Every command below was run on B850 / Knuckles on 2026-08-27 and the output pasted verbatim.
> Where something could not be verified from that node it is marked **UNVERIFIED** rather than
> guessed. Output on your node will differ — the commands are the deliverable, not the values.

---

## 1. START HERE: which deployment path is this node on?

**There are two deployment paths and they run different yt-dlp builds.** This is the first thing to
establish, because it makes every other answer either right or wrong. If you skip it you will read a
version number off the wrong artifact and troubleshoot an extractor bug that is not in your build.

| | `up-yt` (source path) | `up-yt-published` (published path) |
|---|---|---|
| Compose files | `docker-compose.yml` + `docker-compose.yt-cookies.yml` (via `COOKIES_DC`) | `docker-compose.yml` + `docker-compose.integrations.images.yml` (via `DC`) |
| `image:` resolves to | *(empty)* → compose auto-names `pmoves-pmoves-yt` | `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest` |
| Built from | `../PMOVES.YT`, `pmoves_yt_service/Dockerfile` — the **fork**, vendored yt-dlp tree | `pmoves/services/pmoves-yt/Dockerfile` — the **shim**, `pip install yt-dlp[default]` |
| yt-dlp | the fork: CHIT signing, NATS publish, SoundCloud fixes, phase9c multi-client | **n/a — a genuinely pulled published image does not start at all** (§1.3) |
| Cookie volume | yes — `--profile yt-cookies`, `yt-cookies-vol` mounted at `/app/config/cookies` | **no** — see §5.1 |

The published image is built by `.github/workflows/integrations-ghcr.matrix.json`:

```
$ python3 -c "import json;d=json.load(open('.github/workflows/integrations-ghcr.matrix.json'));[print(json.dumps(i,indent=1)) for i in (d if isinstance(d,list) else d.get('include',[])) if i.get('name')=='pmoves-yt']"
{
 "name": "pmoves-yt",
 "context": "pmoves/services/pmoves-yt",
 "dockerfile": "pmoves/services/pmoves-yt/Dockerfile",
 "image_name": "pmoves-yt",
 ...
}
```

Note what that means alongside [`README.md`](./README.md), which describes
`pmoves/services/pmoves-yt` as *"a compatibility mirror/shim, not the source of truth"*. The
published image is built from the **shim**, and the shim's Dockerfile installs yt-dlp from PyPI,
not from the fork:

```
$ grep -n 'yt-dlp' pmoves/services/pmoves-yt/Dockerfile
16:    && if [ -n "$YTDLP_PIP_URL" ]; then pip install --no-cache-dir "$YTDLP_PIP_URL"; \
17:       elif [ -n "$YTDLP_VERSION" ]; then pip install --no-cache-dir "yt-dlp[default]==${YTDLP_VERSION}"; \
18:       else pip install --no-cache-dir "yt-dlp[default]"; fi
```

That PyPI install is real, but it is **not** what you get by pulling the image — because nothing you
pull will start. Read §1.3 before planning any work around the published path.

### 1.1 The discriminator — run all three

**One command is not enough.** Run the image check for intent, and the version check for fact.

```bash
# (a) which image name the container was started from
docker inspect pmoves-pmoves-yt-1 --format '{{.Config.Image}}'

# (b) what yt-dlp is ACTUALLY running (authoritative)
curl -s http://localhost:8077/healthz

# (c) what the recorded submodule pin says it should be
git ls-tree HEAD -- PMOVES.YT
```

Measured on B850 / Knuckles:

```
$ docker inspect pmoves-pmoves-yt-1 --format '{{.Config.Image}}'
pmoves-pmoves-yt

$ curl -s http://localhost:8077/healthz
{"ok":true,"yt_dlp":{"yt_dlp_version":"2026.07.04"},"provenance":{}}

$ git ls-tree HEAD -- PMOVES.YT
160000 commit ebd39b7fc7507298c768fbf64826bd22265dffb0	PMOVES.YT
```

Image is `pmoves-pmoves-yt` — a local build with no registry prefix — so **this node is on the
source path**. Runtime yt-dlp `2026.07.04` matches the pin (§2.2), so the build is in sync with the
gitlink.

Reading it:

- Image name has **no registry prefix** (`pmoves-pmoves-yt`) → source path, locally built.
- Image name is **`ghcr.io/powerfulmoves/pmoves-yt:...`** → published path *was selected*. Confirm
  with (b) before trusting it — see the caveat immediately below.

### 1.2 Caveat: the published overlay does not remove `build:`

`docker-compose.integrations.images.yml` is two lines and overrides **only** `image:`:

```
$ cat pmoves/docker-compose.integrations.images.yml
services:
  pmoves-yt:
    image: ${PMOVES_YT_IMAGE:-ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest}
```

The base service's `build:` block survives the merge. Verified with `docker compose config`:

```
$ docker compose ... -f docker-compose.yml -f docker-compose.integrations.images.yml config   # published
image: 'ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest'
build.context: /home/pmoves-knuckles/pinokio/api/PMOVES.AI/PMOVES.YT

$ docker compose ... -f docker-compose.yml config                                              # source
image: None
build.context: /home/pmoves-knuckles/pinokio/api/PMOVES.AI/PMOVES.YT
```

**Consequence:** on the published path the build context still points at the fork. A node that has
the `PMOVES.YT` submodule checked out can end up with a **locally-built fork image wearing the GHCR
name** rather than the stock-yt-dlp image the name implies. So the image name tells you which target
someone *ran*; only `/healthz` tells you what is *running*.

The image *name* therefore guarantees nothing about the build. That has a second and larger
consequence, which is the subject of §1.3: it is precisely why the broken published artifact has
never been noticed — the target named after it does not pull it.

Do **not** try to settle this with `RepoDigests` — it does not discriminate. This node's
locally-built image carries one:

```
$ docker image inspect pmoves-pmoves-yt --format 'RepoDigests={{.RepoDigests}}'
RepoDigests=[pmoves-pmoves-yt@sha256:bf62dae405a0ebf85ef31f7fd987408414ce87cf1b1d80b05e9e1f8aa760c05d]
```

**UNVERIFIED:** whether the tag `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest` exists in the
registry at all. `docker manifest inspect` returns `denied` anonymously and
`gh api users/POWERFULMOVES/packages/container/pmoves-yt/versions` returns
`403 ... needs at least read:packages scope`, so an operator cannot inspect the tag without a
`read:packages` token. What the artifact *would do* if pulled is **not** unverified — that is
settled from the Dockerfile and shim in this repo, and it is a startup crash. See §1.3.

### 1.3 DEFECT: the published image cannot start — it is not a deployable artifact

`ghcr.io/powerfulmoves/pmoves-yt:*` builds green and is unrunnable. Its entrypoint is
`uvicorn yt:app`, and `yt.py` is a shim that walks **three directory levels up** to find the
submodule runtime:

```
$ grep -nE 'WORKDIR|^COPY \. \.|^CMD' pmoves/services/pmoves-yt/Dockerfile
3:WORKDIR /app
19:COPY . .
52:CMD ["uvicorn","yt:app","--host","0.0.0.0","--port","8077"]

$ sed -n '9p' pmoves/services/pmoves-yt/yt.py
_SUBMODULE_ROOT = pathlib.Path(__file__).resolve().parents[3] / "PMOVES.YT"
```

`parents[3]` is written for the **repo** layout, where `pmoves/services/pmoves-yt/yt.py` sits exactly
three levels below the repo root. `COPY . .` into `WORKDIR /app` flattens those three levels away: in
the image the file is `/app/yt.py`, whose `.parents` is `['/app', '/']` — length 2.

Reproduce it in ten seconds, from the repo root — this places the shim at the same path depth the
image does, with no build required:

```bash
mkdir -p /tmp/ytshim && cp pmoves/services/pmoves-yt/yt.py /tmp/ytshim/
docker run --rm -v /tmp/ytshim:/app:ro -w /app python:3.11-slim python -c "import yt"
```

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/app/yt.py", line 9, in <module>
    _SUBMODULE_ROOT = pathlib.Path(__file__).resolve().parents[3] / "PMOVES.YT"
                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "/usr/local/lib/python3.11/pathlib.py", line 445, in __getitem__
    raise IndexError(idx)
IndexError: 3
$ echo $?
1
```

The `IndexError` fires on line 9, before any of the shim's own fallbacks (`if _IMPL.exists():`, the
`yt_dlp = SimpleNamespace(...)` guard) can run. `yt:app` is never defined and uvicorn dies at
startup.

**Correcting the path depth alone would not fix it.** The GHCR build context is
`pmoves/services/pmoves-yt`, and `PMOVES.YT` is a repo-root submodule — it is not in the context, so
a corrected path would have nothing to import:

```
$ ls pmoves/services/pmoves-yt/ | grep -i 'PMOVES.YT' || echo "NOT PRESENT in the build context"
NOT PRESENT in the build context
```

#### 1.3.1 Why this survived five months

1. **Publishing is inherited, not deliberate.** `pmoves-yt` has been in
   `integrations-ghcr.matrix.json` since `6d90e4d10` (#699, 2026-02-23), when
   `pmoves/services/pmoves-yt/yt.py` was a real, self-contained 3745-line service. `731244086`
   (#883, 2026-03-12) replaced it with the three-levels-up shim and changed **neither** the
   Dockerfile nor the matrix entry. Every revision in the Dockerfile's history uses `WORKDIR /app`
   with `COPY . .`, so there is no earlier layout at which the shim resolved inside a container — it
   has never worked in an image.
2. **CI structurally cannot catch it.** The defect is at *runtime import*, not build. The image
   builds and pushes clean — recent `integrations-ghcr.yml` runs are `success` — and the matrix has
   no step that starts the container.
3. **Nothing ever pulls it.** Per §1.2 the images overlay replaces only `image:`, leaving `build:`
   pointed at the fork. So `up-yt-published` on a node with the submodule checked out **rebuilds the
   fork locally and tags it with the GHCR name**. The broken artifact is bypassed by the very target
   named after it.

#### 1.3.2 What to do about it

- **Operators:** do not plan around `up-yt-published` as a way to run stock yt-dlp. On a node with
  `PMOVES.YT` checked out it silently hands you the fork; on a node without it, a genuine pull hands
  you a container that will not start. Use `up-yt`, and use §1.1 (b) to read what is actually
  running.
- **Maintainers — the finding:** `pmoves-yt` **should not be published in its current form.** Fixing
  the shim means moving the build context to the repo root and vendoring the submodule into the
  image, which yields a *fork* image under a name whose whole stated purpose was to be stock PyPI —
  it removes the reason the entry exists. Dropping the `pmoves-yt` entry from
  `integrations-ghcr.matrix.json`, along with the `docker-compose.integrations.images.yml` override
  and the two Make targets that point at it (`up-yt-published` at `Makefile:2582`,
  `up-yt-published-amd` at `Makefile:2586`), is the smaller and more honest change.
  **No code change is made here — this is a docs branch.** Tracked in
  [#2802](https://github.com/POWERFULMOVES/PMOVES.AI/issues/2802).

> **This voids [`YTDLP_CURRENCY.md`](./YTDLP_CURRENCY.md) §1b's mapping** of
> `ghcr.io/powerfulmoves/pmoves-yt:...` → "published image (stock PyPI yt-dlp)". There is no state in
> which that image serves stock PyPI yt-dlp: pulled, it does not start; locally rebuilt under that
> name, it is the fork. Both documents still agree on the rule that matters — **when the layers
> disagree, the running container wins** — and §1.1 (b) is how you settle it.

---

## 2. Reading the submodule pin correctly

### 2.1 Use `git ls-tree`, never `git ls-files -s`

```bash
git ls-tree HEAD -- PMOVES.YT          # correct — reads the commit
git -C PMOVES.YT rev-parse HEAD        # what is actually checked out
```

`git ls-files -s` reads the **index**, which lies the moment anything is staged. A detached HEAD in
the submodule is **normal** and is not drift by itself — drift is when these two disagree.

[`YTDLP_CURRENCY.md`](./YTDLP_CURRENCY.md) §1a covers the pin-reading mechanism in full, including
the working-checkout-vs-pin trap and how to count drift across the fleet. Go there for
"what version *should* ship"; stay here for "my node is misbehaving right now".

### 2.2 HAZARD: `git submodule update --remote` downgrades the extractor set

`.gitmodules` declares a branch that is **five months behind the recorded pin**:

```
$ git config -f .gitmodules --get submodule.PMOVES.YT.branch
PMOVES.AI-Edition-Hardened

$ git -C PMOVES.YT show origin/PMOVES.AI-Edition-Hardened:yt_dlp/version.py | grep __version__
__version__ = '2026.02.04'

$ git -C PMOVES.YT rev-parse HEAD
ebd39b7fc7507298c768fbf64826bd22265dffb0

$ git -C PMOVES.YT branch -a --contains ebd39b7fc7507298c768fbf64826bd22265dffb0
* feat/upstream-sync-2026.07
  remotes/origin/feat/upstream-sync-2026.07

$ git -C PMOVES.YT show HEAD:yt_dlp/version.py | grep __version__
__version__ = '2026.07.04'
```

The pin sits on the **unmerged** `feat/upstream-sync-2026.07` (yt-dlp `2026.07.04`); the declared
tracking branch is on `2026.02.04`. `--remote` resolves the *declared branch*, so:

```bash
git submodule update --remote PMOVES.YT     # <-- DO NOT. Moves the pin BACK five months.
```

Use the plain form, which honours the recorded gitlink:

```bash
git submodule update --init PMOVES.YT
```

If you have already run `--remote`, `/healthz` will report `2026.02.04` after a rebuild. Restore
with:

```bash
git submodule update --init --force PMOVES.YT     # then rebuild
```

**Do not reach for `git checkout -- PMOVES.YT`.** It restores the superproject's *gitlink* — which
`--remote` never changed — and leaves the submodule's own HEAD sitting on the downgraded commit, so
the next rebuild still picks up the old extractor set. It is a no-op for this failure, not a partial
fix. Verified on a throwaway two-repo fixture (git 2.43.0) that reproduces the shape of this
hazard — a submodule pinned at an unmerged newer commit while `.gitmodules` declares an older
branch:

```
### the hazard: git submodule update --remote SUB
  gitlink(HEAD) 3e8fcf3   SUB HEAD f500dc2   SUB content v1-OLD   status [ M SUB]

### git checkout -- SUB
  gitlink(HEAD) 3e8fcf3   SUB HEAD f500dc2   SUB content v1-OLD   status [ M SUB]   <-- unchanged

### git submodule update --init --force SUB
  gitlink(HEAD) 3e8fcf3   SUB HEAD 3e8fcf3   SUB content v2-NEW   status []         <-- restored
```

Plain `git submodule update --init PMOVES.YT` also restores it **when the submodule working tree is
clean**, and that remains the form to prefer day to day. It is the wrong form to *document for
recovery*, because it aborts outright if anything inside the submodule has been edited:

```
$ git submodule update --init SUB          # with one local edit inside SUB
error: Your local changes to the following files would be overwritten by checkout:
	version.txt
fatal: Unable to checkout '3e8fcf3' in submodule path 'SUB'
$ echo $?
1
```

`--force` discards those edits and completes. That is the right trade when you are recovering from
an accidental `--remote`, but it *does* discard them — check `git -C PMOVES.YT status` first if you
might have work in there.

---

## 3. Bring-up

Use the Known Roads. A `PreToolUse` governance hook blocks raw compose lifecycle verbs — its matcher
is narrow and specific:

```
$ grep -n 'RAW_COMPOSE' .claude/hooks/governance/known-roads-enforcer.py
22:RAW_COMPOSE = re.compile(r'docker[\s]+compose[\s]+(up|restart|down)\b')
37:    if RAW_COMPOSE.search(command) and not MAKE_WRAPPER.search(command):
```

Only `up`, `restart`, `down` are blocked. `docker compose ps|logs|config|stop` are **not** blocked,
which matters for §6 (logs) and §8 (teardown).

All six variants (`make -C pmoves <target>`):

| Node | Source path (fork yt-dlp) | Published path (GHCR) | Hardened |
|---|---|---|---|
| NVIDIA / CPU | `up-yt` | `up-yt-published` | `up-yt-hardened` |
| **AMD / ROCm** | `up-yt-amd` | `up-yt-published-amd` | `up-yt-hardened-amd` |

```bash
make -C pmoves up-yt                    # Makefile:2551
make -C pmoves up-yt-amd                # Makefile:2560
make -C pmoves up-yt-published          # Makefile:2582
make -C pmoves up-yt-published-amd      # Makefile:2586
make -C pmoves up-yt-hardened           # Makefile:2654
make -C pmoves up-yt-hardened-amd       # Makefile:2659
```

> **Prefer the source path.** The two `*-published*` targets are listed for completeness, not as a
> recommendation. The image they name cannot start (§1.3), and on a node that has the `PMOVES.YT`
> submodule present they quietly rebuild the fork under the GHCR name instead (§1.2). Either way you
> are not running what the target's name implies.
> See [#2802](https://github.com/POWERFULMOVES/PMOVES.AI/issues/2802).

Inspect any target before running it — `make -n` expands the full compose chain without executing:

```bash
make -C pmoves -n up-yt
```

### 3.1 HAZARD: AMD/ROCm nodes must use the `-amd` targets

`ffmpeg-whisper` declares an NVIDIA device reservation in `docker-compose.yml`. On a node with no
NVIDIA container runtime it does not fall back — it **fails to schedule outright**:

```
could not select device driver "nvidia" with capabilities: [[gpu]]
```

The `-amd` siblings inject `docker-compose.amd.yml`, which resets the reservation so the image runs
its CPU path (`devices: !reset []`, `WHISPER_DEVICE=cpu`). Confirm the overlay is in the chain:

```
$ make -C pmoves -n up-yt-amd | grep -c 'docker-compose.amd.yml'
2
```

`make -n up-yt` returns `0` for the same grep — NVIDIA nodes are untouched by default. Wired in
#2798; before that the overlay existed but no Make target referenced it.

Confirm a running whisper container is genuinely on the CPU path:

```
$ docker inspect pmoves-ffmpeg-whisper-1 --format 'Runtime={{.HostConfig.Runtime}} DeviceReqs={{.HostConfig.DeviceRequests}}'
Runtime=runc DeviceReqs=[]
```

Empty `DeviceRequests` = no GPU requested. A populated one on an AMD node is the misconfiguration.

### 3.2 Optional overlays

- **JuiceFS media** — `up-yt` appends `docker-compose.yt-media.yml` automatically, but **only** when
  `JUICEFS_HOST_MOUNT` is set. Its `rshared` bind is host-topology-specific and fails on nodes
  without a host-side FUSE mount. Leave unset unless you have one.
- **Pinning a published version** — `PMOVES_YT_IMAGE=ghcr.io/powerfulmoves/pmoves-yt:<tag> make -C pmoves up-yt-published`.

---

## 4. Health verification

### 4.1 Liveness

```bash
curl -s http://localhost:8077/healthz     # pmoves-yt
curl -s http://localhost:8078/healthz     # ffmpeg-whisper
```

```
$ curl -s http://localhost:8077/healthz
{"ok":true,"yt_dlp":{"yt_dlp_version":"2026.07.04"},"provenance":{}}

$ curl -s http://localhost:8078/healthz
{"ok":true}
```

Container-level view:

```
$ docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -Ei 'yt|whisper|pot'
pmoves-pmoves-yt-1	pmoves-pmoves-yt	Up 7 hours (healthy)
pmoves-ffmpeg-whisper-1	pmoves-ffmpeg-whisper	Up 7 hours (healthy)
pmoves-bgutil-pot-provider-1	brainicism/bgutil-ytdlp-pot-provider:1.2.2	Up 12 days
pmoves-yt-cookie-writer-1	pmoves-yt-cookie-writer	Up 12 days (healthy)
pmoves-yt-cookie-refresher-1	pmoves-yt-cookie-refresher	Up 12 days (healthy)
```

Published ports (all loopback-bound by default):

```
$ for c in pmoves-pmoves-yt-1 pmoves-ffmpeg-whisper-1 pmoves-bgutil-pot-provider-1 pmoves-yt-cookie-refresher-1 pmoves-yt-cookie-writer-1; do printf '%-32s %s\n' "$c" "$(docker port $c 2>/dev/null | tr '\n' ' ')"; done
pmoves-pmoves-yt-1               8077/tcp -> 127.0.0.1:8077
pmoves-ffmpeg-whisper-1          8078/tcp -> 127.0.0.1:8078
pmoves-bgutil-pot-provider-1
pmoves-yt-cookie-refresher-1     8115/tcp -> 127.0.0.1:8115
pmoves-yt-cookie-writer-1
```

`bgutil-pot-provider` and `yt-cookie-writer` publish **no host port** by design — reach them from
inside the network (§5.3).

### 4.2 Functional — does extraction actually work?

Liveness proves the process is up. It does **not** prove YouTube extraction works. This does:

```bash
make -C pmoves yt-docs-catalog-smoke     # extractor set loaded
make -C pmoves yt-jellyfin-smoke         # real network extraction
```

```
$ make -C pmoves yt-docs-catalog-smoke
→ Hitting http://localhost:8077/yt/docs/catalog
{
  "ok": true,
  "meta": {
    "yt_dlp_version": "2026.07.04",
    "extractor_count": 1751
  },
  "counts": {
    "options": 250,
    "groups": 16
  }
}
```

`extractor_count: 1751` is a useful canary — a collapsed count means a broken or partial build.

```
$ make -C pmoves yt-jellyfin-smoke
[PASS] pmoves-yt-health: http://localhost:8077/healthz -> 200
[FAIL] jellyfin-bridge-health: http://localhost:8093/healthz unreachable (<urlopen error [Errno 111] Connection refused>)
[PASS] yt-info: id=dQw4w9WgXcQ title=Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)

Summary: FAIL (1 checks)
```

Read that carefully: **extraction passed**; the Jellyfin bridge on `:8093` is simply not running on
this node. The target exits non-zero on the bridge alone. If you only care about ingest, the
`yt-info` line is your signal.

`make -C pmoves yt-docs-sync` (`POST /yt/docs/sync`) captures yt-dlp help/extractors into Supabase —
run it after a version bump so the catalog reflects the new build.

Single extraction by hand (`/yt/info` is **POST** — a GET returns `Method Not Allowed`):

```bash
curl -s -X POST http://localhost:8077/yt/info \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

```
{"ok":true,"info":{"id":"dQw4w9WgXcQ","title":"Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)","uploader":"Rick Astley","duration":213,"webpage_url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}}
```

Full route list:

```bash
curl -s http://localhost:8077/openapi.json \
  | python3 -c "import sys,json;print('\n'.join(sorted(json.load(sys.stdin)['paths'])))"
```

includes `/yt/ingest`, `/yt/download`, `/yt/search`, `/yt/channel`, `/yt/playlist`, `/yt/summarize`,
`/yt/chapters`, `/yt/emit`, `/yt/docs/{sync,catalog}`, `/yt/control/*`, `/metrics`.

---

## 5. The cookie chain

Three cooperating pieces, plus a PO-token provider:

| Service | Role | Down means |
|---|---|---|
| `yt-cookie-refresher` (`:8115`) | Weekly Playwright harvest → encrypt → store in Supabase → NATS notify | Cookies go stale; no new harvest. An existing cookie file keeps working until expiry. |
| `yt-cookie-writer` (no port) | NATS subscriber → decrypt → write `/cookies/yt-cookies.txt` into `yt-cookies-vol` | Harvested cookies never reach `pmoves-yt`. Silent — see §5.2. |
| `bgutil-pot-provider` (`:4417`, internal) | PO token minting for yt-dlp | PO-token-gated videos fail; non-gated extraction still works. |

`pmoves-yt` reads the cookiefile **per request**, so a cookie update needs no restart.

### 5.1 Is the cookie chain actually wired into `pmoves-yt`?

The single most informative check — read `YT_COOKIES` inside the running container:

```bash
docker exec pmoves-pmoves-yt-1 sh -c 'echo $YT_COOKIES'
docker exec pmoves-pmoves-yt-1 sh -c 'ls -la /app/config/cookies/'
```

```
$ docker exec pmoves-pmoves-yt-1 sh -c 'echo $YT_COOKIES'
/app/config/cookies/darkxside.youtube.cookies.txt

$ docker exec pmoves-pmoves-yt-1 sh -c 'ls -la /app/config/cookies/'
total 12
drwxrwxr-x  2 1000 1000 4096 May 15 19:59 .
drwxrwxr-x 19 1000 1000 4096 Aug 27 23:36 ..
-rw-rw-r--  1 1000 1000   14 May 15 19:59 .gitignore
```

**Interpretation:**

- `YT_COOKIES=/app/config/cookies/yt-cookies.txt` → the `yt-cookies` overlay **is** applied. Good.
- `YT_COOKIES=.../darkxside.youtube.cookies.txt` → that is the **base-compose placeholder**. The
  overlay was **not** applied; this container is running cookie-less.

On this node it is the placeholder, **and the file does not exist** — the directory holds only
`.gitignore`. So `pmoves-yt` here is running with no cookies at all. Confirmed structurally by the
mount list — a plain bind of `pmoves/config`, with no `yt-cookies-vol` anywhere:

```
$ docker inspect pmoves-pmoves-yt-1 --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
bind /home/pmoves-knuckles/pinokio/api/PMOVES.AI/pmoves/config -> /app/config
volume /var/lib/docker/volumes/pmoves_pmoves-yt-data/_data -> /data
```

This is exactly the state the `up-yt` recipe warns about in its own comment — the overlay carries
the volume, and any bring-up that omits `--profile yt-cookies` starts `pmoves-yt` without it:

```
# COOKIES_DC (base + yt-cookies overlay), NOT $(DC): STACK_FILES omits the
# overlay, so plain DC starts pmoves-yt WITHOUT the harvested-cookie volume
# (/app/config/cookies) - downloads then run cookie-less and bot-gate.
```

Note this applies to **`up-yt-published` and `up-yt-hardened` as written**: both use `$(DC)` and
neither passes `--profile yt-cookies`. Cookie-less operation is the *expected* state on the
published and hardened paths, not a fault. Extraction still worked here (§4.2) — cookies matter for
age/region-gated and bot-gated videos, not for everything.

Remedy on the source path:

```bash
make -C pmoves up-yt-cookies              # start refresher + writer
make -C pmoves up-yt                      # restart pmoves-yt WITH the overlay
```

When the overlay *is* applied it also overrides the container command to load a harvested PO token
from `/app/config/cookies/yt-po-token.txt` at launch; if that file is absent it logs
`No harvested PO token — bgutil-pot-provider remains active` and continues.

### 5.2 HAZARD: `yt-cookie-writer` reports healthy while its NATS subscription is dead

Its healthcheck asserts only that a file exists:

```yaml
test: ["CMD", "python", "-c", "from pathlib import Path; assert Path('/tmp/healthy').exists()"]
```

`main.py` touches `/tmp/healthy` **once**, after the NATS subscription first succeeds, and nothing
ever removes it. If NATS later goes away, the file remains and the container stays `healthy`
forever. Measured here:

```
$ docker logs --timestamps --tail 1 pmoves-yt-cookie-writer-1
2026-08-27T14:10:15.231993436Z socket.gaierror: [Errno -3] Temporary failure in name resolution

$ docker inspect pmoves-yt-cookie-writer-1 --format '{{.State.Health.Status}} | failing streak: {{.State.Health.FailingStreak}} | restarts: {{.RestartCount}}'
healthy | failing streak: 0 | restarts: 0

$ docker exec pmoves-yt-cookie-writer-1 sh -c 'ls -la /tmp/healthy'
-rw-r--r-- 1 root root 0 Aug 15 05:11 /tmp/healthy
```

A DNS failure **today** (Aug 27), a health marker from **Aug 15**, zero restarts, and status
`healthy`. The failure was a NATS outage window — `nats` resolves again now, and the process is
still alive:

```
$ docker exec pmoves-yt-cookie-writer-1 python3 -c "import socket;print(socket.gethostbyname('nats'))"
172.30.6.2

$ docker top pmoves-yt-cookie-writer-1
UID    PID    PPID   C  STIME  TTY  TIME      CMD
root   5948   5898   0  Aug15  ?    00:00:04  python main.py
```

**Do not trust `healthy` for this container.** Check the log tail instead:

```bash
docker logs --timestamps --tail 20 pmoves-yt-cookie-writer-1
```

**UNVERIFIED:** whether this writer re-subscribed to NATS after the bus came back. Proving it
requires publishing a cookie-update message, which was out of scope. If in doubt, force a clean
resubscribe:

```bash
make -C pmoves up-yt-cookies-recreate
```

### 5.3 Checking `bgutil-pot-provider`

No host port. Reach it from a container on the same network:

```bash
docker exec pmoves-pmoves-yt-1 python3 -c \
  "import urllib.request;print(urllib.request.urlopen('http://bgutil-pot-provider:4417/ping',timeout=5).read())"
```

```
b'{"server_uptime":1108444.290234754,"version":"1.2.2"}'
```

### 5.4 Cookie lifecycle targets (`pmoves/mk/yt-cookies.mk`)

```bash
make -C pmoves yt-cookies-check       # preflight: OAuth + Supabase env vars
make -C pmoves yt-cookies-auth        # one-time OAuth consent (opens a browser)
make -C pmoves yt-cookies-bootstrap   # consent + first harvest, one click
make -C pmoves yt-cookies-refresh     # force a harvest now
make -C pmoves yt-cookies-status      # vault + cookie state
make -C pmoves yt-cookies-revoke      # remove vault entry, force re-consent
```

`yt-cookies-status` runs on the **host**, not in a container — and the tool already knows that.
`tools/yt_oauth_flow.py::_supabase_url()` rewrites the in-network Kong hostname before the request:

```
$ sed -n '127,132p' pmoves/tools/yt_oauth_flow.py
    url = _env("SUPABASE_URL", _env("SUPA_REST_URL", "http://localhost:8000"))
    # This tool always runs on the host (via `make yt-cookies-auth`), not in a
    # container. The tier env files set SUPABASE_URL=http://supabase-kong:8000
    # which is the in-compose hostname and won't resolve from the host process.
    if "supabase-kong" in url:
        url = url.replace("supabase-kong", "localhost")
```

So **`supabase-kong` cannot be the cause of a name-resolution failure here**, and diagnosing it as
such will send you after the wrong thing. With the tier env files loaded it resolves correctly and
the target succeeds:

```
$ bash scripts/with-env.sh python3 -c "...print(os.environ['SUPABASE_URL']); print(m._supabase_url())"
http://supabase-kong:8000
http://localhost:8000

$ make -C pmoves yt-cookies-status
=== YT Cookies: status ===
No OAuth credentials stored.
Run: make yt-cookies-auth
$ echo $?
0
```

**HAZARD: the failure that does happen, and what actually causes it.** Running the same target from
a **linked git worktree** produced:

```
$ make yt-cookies-status          # run from a worktree
=== YT Cookies: status ===
...
httpx.ConnectError: [Errno -2] Name or service not known
make: *** [mk/yt-cookies.mk:59: yt-cookies-status] Error 1
```

`env.shared` and `env.tier-*` are untracked, so they exist only in the **primary** working tree.
`scripts/with-env.sh` resolves `ROOT_DIR` from `BASH_SOURCE`, finds none of them in the worktree, and
leaves `SUPABASE_URL` unset. The lookup then falls through to whatever `SUPA_REST_URL` the **ambient
shell** exports — and the rewrite above special-cases only `supabase-kong`, so anything else passes
through untouched:

```
$ echo "$SUPA_REST_URL"
http://host.docker.internal:54321/rest/v1

$ python3 -c "import socket; socket.gethostbyname('host.docker.internal')"
socket.gaierror: [Errno -2] Name or service not known

$ env -u SUPA_REST_URL bash scripts/with-env.sh python3 -c "...print(m._supabase_url())"
http://localhost:8000
```

`host.docker.internal` is a Docker-Desktop-only name and does not exist on a Linux host. The errno is
the tell: `host.docker.internal` gives **`[Errno -2] Name or service not known`** — the error
actually observed — while `supabase-kong` gives **`[Errno -3] Temporary failure in name
resolution`**. Different errno, different cause.

Triage in this order, and do **not** stop at "the hostname is in-network":

1. **Run it from the primary working tree.** The env files are untracked and do not exist in
   worktrees.
2. **Check for an ambient override:** `echo "$SUPABASE_URL" "$SUPA_REST_URL" "$YT_OAUTH_REST_URL"`.
   An exported value beats the env files. `env -u SUPA_REST_URL make -C pmoves yt-cookies-status`
   confirms or clears it in one shot.
3. **Check Kong is up on the host port:**
   `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/rest/v1/` should return `401`
   (route present, apikey required). `000` means nothing is listening; `404` means Kong is up but
   has no `/rest/v1` route, which is a different and much more misleading failure.
4. Only then suspect the cookie pipeline. `No OAuth credentials stored.` is a **successful** run
   reporting an empty vault, not a failure.

Escape hatch: `YT_OAUTH_REST_URL` points the tool straight at PostgREST, bypassing Kong entirely.

---

## 6. Logs

There is no file-based log tree for these services — everything goes to the container log driver.

```bash
docker logs --timestamps --tail 100 pmoves-pmoves-yt-1
docker logs --timestamps --tail 100 pmoves-ffmpeg-whisper-1
docker logs --timestamps --tail 100 pmoves-yt-cookie-writer-1
docker logs --timestamps --tail 100 pmoves-yt-cookie-refresher-1
docker logs --timestamps --tail 100 pmoves-bgutil-pot-provider-1

# follow several at once. `logs` is not blocked by the governance hook (§3), and with `-p pmoves`
# it needs no `-f <file>` and no particular cwd -- but read the coverage caveat below.
docker compose -p pmoves logs -f --tail 50 pmoves-yt ffmpeg-whisper
```

**Why there is no `-f <compose-file>` and no `cd`.** For `logs`, `ps`, `stop`, `start` and `kill`,
Compose selects containers by the **project label on what is already running**, not from the service
list in a compose file. The command above therefore works unchanged from the repo root, where there
is no compose file at all:

```
$ ls docker-compose.y*ml compose.y*ml
ls: cannot access 'docker-compose.y*ml': No such file or directory

$ docker compose -p pmoves logs -f --tail 50 pmoves-yt ffmpeg-whisper bgutil-pot-provider
pmoves-yt-1  | ConnectionRefusedError: [Errno 111] Connection refused
...
```

That is also why the cookie pair (defined only in `docker-compose.yt-cookies.yml`) is reachable
without layering that file in — see §8.

**HAZARD: the selection fails silently.** A name Compose cannot match is skipped with no message and
exit 0. There is no `no such service` error to warn you:

```
$ docker compose --dry-run -p pmoves stop definitely-not-a-service
$ echo $?
0
```

That bites on `bgutil-pot-provider`, which on this node is running **without** Compose labels — it
was started outside the project — even though `docker-compose.yml:2724` defines it:

```
$ docker ps --format '{{.Names}}' | grep -Ei 'yt|whisper|pot' | while read -r c; do \
    printf '%-32s project=%-8s service=%s\n' "$c" \
      "$(docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.project"}}')" \
      "$(docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.service"}}')"; done
pmoves-pmoves-yt-1               project=pmoves   service=pmoves-yt
pmoves-ffmpeg-whisper-1          project=pmoves   service=ffmpeg-whisper
pmoves-bgutil-pot-provider-1     project=         service=
pmoves-yt-cookie-writer-1        project=pmoves   service=yt-cookie-writer
pmoves-yt-cookie-refresher-1     project=pmoves   service=yt-cookie-refresher
```

**Confirm coverage before trusting any multi-service Compose command.** An empty result means that
name is a silent no-op:

```
$ for s in pmoves-yt ffmpeg-whisper bgutil-pot-provider yt-cookie-writer yt-cookie-refresher; do \
    printf '  %-22s -> [%s]\n' "$s" "$(docker compose -p pmoves ps --format '{{.Name}}' "$s" | tr '\n' ' ')"; done
  pmoves-yt              -> [pmoves-pmoves-yt-1 ]
  ffmpeg-whisper         -> [pmoves-ffmpeg-whisper-1 ]
  bgutil-pot-provider    -> [ ]
  yt-cookie-writer       -> [pmoves-yt-cookie-writer-1 ]
  yt-cookie-refresher    -> [pmoves-yt-cookie-refresher-1 ]
```

For anything Compose does not own, address the container directly —
`docker logs --timestamps --tail 100 pmoves-bgutil-pot-provider-1`, the per-container form listed
above, which always works.

**Always pass `--timestamps`.** §5.2 is only diagnosable because timestamps showed a *today* error
sitting behind an *Aug 15* health marker.

`yt-cookie-refresher` logs its own healthcheck polls at INFO, so its tail is mostly
`GET /healthz 200` noise. Filter it:

```bash
docker logs --tail 200 pmoves-yt-cookie-refresher-1 2>&1 | grep -v '/healthz'
```

---

## 7. Common failures, by the symptom you actually see

| Symptom | Cause | Check | Fix |
|---|---|---|---|
| `could not select device driver "nvidia"`, `ffmpeg-whisper` never starts | AMD/ROCm node on a non-`-amd` target | `docker inspect pmoves-ffmpeg-whisper-1 --format '{{.HostConfig.DeviceRequests}}'` | Use `up-yt-amd` / `up-yt-published-amd` / `up-yt-hardened-amd` (§3.1) |
| `/healthz` reports a yt-dlp five months older than expected | Someone ran `git submodule update --remote` | §2.2 | `git submodule update --init --force PMOVES.YT`, rebuild. **Not** `git checkout -- PMOVES.YT` — no-op (§2.2) |
| An extractor bug you *know* is fixed in the fork is still present | Stale local image, or a build that ran from the shim rather than the fork | §1.1 (b) — trust `/healthz`, never the image name | Rebuild via `up-yt`. The published path is not a working alternative (§1.3) |
| Bot-gate / "Sign in to confirm you're not a bot" / age-gate failures | `pmoves-yt` running cookie-less | `docker exec pmoves-pmoves-yt-1 sh -c 'echo $YT_COOKIES'` → placeholder name (§5.1) | `make -C pmoves up-yt-cookies && make -C pmoves up-yt` |
| Cookies harvested but never take effect; writer says `healthy` | Writer's NATS subscription dropped; healthcheck cannot see it | `docker logs --timestamps --tail 20 pmoves-yt-cookie-writer-1` | `make -C pmoves up-yt-cookies-recreate` (§5.2) |
| PO-token-gated videos fail, others fine | `bgutil-pot-provider` down or unreachable | §5.3 ping | Restart it via the bring-up target |
| `yt-cookies-status` → `httpx.ConnectError: [Errno -2] Name or service not known` | Ambient `SUPA_REST_URL`, or run from a worktree that has no env files. **Not** `supabase-kong` — the tool rewrites that | §5.4 triage list, in order | Run from the primary tree; `env -u SUPA_REST_URL make -C pmoves yt-cookies-status` |
| A `docker compose -p pmoves stop`/`logs` names a service and nothing happens | Container carries no Compose labels, or the name is wrong — selection skips it silently at exit 0 | `docker compose -p pmoves ps <service>` returns empty (§6) | Address the container directly: `docker stop`/`docker logs <container>` |
| `yt-jellyfin-smoke` FAILs but `yt-info` PASSes | Jellyfin bridge `:8093` not running | Read the per-check lines, not just `Summary:` | Start the bridge, or ignore if ingest-only (§4.2) |
| `Method Not Allowed` from `/yt/info` | Sent a GET | — | It is **POST** (§4.2) |
| `extractor_count` far below ~1751 | Broken or partial build | `make -C pmoves yt-docs-catalog-smoke` | Rebuild; verify the submodule pin first (§2) |
| `pmoves-yt` will not start, `MINIO_USER`/`MINIO_PASSWORD` error | Brand defaults never generated | compose declares `${MINIO_USER:?Run make brand-defaults}` | `make -C pmoves brand-defaults` |

### 7.1 HAZARD: `make seed-data` destroys `pmoves_chunks_qwen3`

Not part of YT bring-up, but reachable from adjacent runbooks and destructive. `seed_local.py`
calls `recreate_collection` on the **production** collection name at `QDRANT_COLLECTION_DIM`
default **384** (a MiniLM demo width) against a 2560d standard, **swallowing all errors**. That is
how the collection went from 700 points / 2560d to 0 points / 384d. **Do not run `make seed-data`
on a node with live vector data.**

---

## 8. Teardown

**There is no `down-yt` Known Road.**

```
$ grep -c 'down-yt:' pmoves/Makefile
0
```

The available options, safest first. The governance hook blocks only `up|restart|down` (§3), so
`stop` is permitted:

```bash
# 1. Stop the Compose-owned YT services, keeping containers, volumes and cookies intact
docker compose -p pmoves stop pmoves-yt ffmpeg-whisper

# 2. The cookie pair. These are defined ONLY in docker-compose.yt-cookies.yml, but no `-f` is
#    needed: `stop` selects by project label on running containers, not from a compose file (§6).
docker compose -p pmoves stop yt-cookie-writer yt-cookie-refresher

# 3. bgutil-pot-provider is Compose-unowned on this node (§6) -- stop it directly.
docker stop pmoves-bgutil-pot-provider-1

# 4. Any single container
docker stop pmoves-pmoves-yt-1
```

Step 2 verified with `--dry-run`, which resolves the selection without touching the containers:

```
$ docker compose --dry-run -p pmoves stop yt-cookie-writer yt-cookie-refresher
 Container pmoves-yt-cookie-writer-1 Stopping
 Container pmoves-yt-cookie-writer-1 Stopped
 Container pmoves-yt-cookie-refresher-1 Stopping
 Container pmoves-yt-cookie-refresher-1 Stopped
$ echo $?
0
```

Same result from the repo root and from `pmoves/`. What it does **not** cover is
`bgutil-pot-provider`: the same dry-run for `pmoves-yt ffmpeg-whisper bgutil-pot-provider` lists only
the first two and still exits `0`. Hence step 3. Run the §6 coverage check whenever you need
certainty that a stop actually reached everything you named.

`make -C pmoves down-all` exists but stops **every** PMOVES service in reverse dependency order —
far broader than the YT chain. Do not reach for it to stop YT.

**Never `docker compose down -v`** on this project: `-v` removes named volumes, which includes
`yt-cookies-vol` (harvested cookies) and `pmoves-yt-data`. Recovering cookies means a fresh OAuth
consent flow (`make -C pmoves yt-cookies-bootstrap`).

Restart after a stop by re-running the bring-up target for **your** path (§3) — this also
re-applies the correct overlays, which a bare `docker start` does not.

---

## 9. Summary of UNVERIFIED items

Recorded rather than guessed:

1. **Registry contents only.** Whether the tag `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest`
   currently exists could not be confirmed — `docker manifest inspect` → `denied`;
   `gh api users/POWERFULMOVES/packages/container/pmoves-yt/versions` →
   `403 ... read:packages scope`. This is **not** an open question about what the artifact does:
   §1.3 settles that from the Dockerfile and shim in this repo and reproduces the startup crash at
   the container's path depth. The defect is tracked for fix in
   [#2802](https://github.com/POWERFULMOVES/PMOVES.AI/issues/2802).
2. **Whether `yt-cookie-writer` re-subscribed** to NATS after the bus returned (§5.2). Proving it
   needs a published cookie-update message.
3. **Published/hardened-path behaviour end-to-end.** This node runs the source path;
   `up-yt-published`, `up-yt-published-amd`, `up-yt-hardened`, `up-yt-hardened-amd` were verified by
   reading their Makefile recipes and `make -n` expansion, **not** by execution. Their compose-file
   chains and the AMD overlay injection are verified; their runtime behaviour is not.
4. **`/metrics` content.** The endpoint is routed, but no `yt_`-prefixed series were present on this
   node at the time of writing.
5. **Whether `bgutil-pot-provider` is Compose-unowned beyond this node** (§6). Here it carries no
   `com.docker.compose.*` labels despite being defined at `docker-compose.yml:2724`, so something
   started it outside the project. A node brought up cleanly via `make -C pmoves up-yt` should have
   it labelled and selectable. Not checked on any other node — run the §6 coverage check on yours
   rather than assuming either way.
