# E2B Danger Room — self-host runbook

**Owning node: `pmoves-5090`.** Not "an operator", not "someone with a GPU box",
not "whoever picks it up". One named node owns the bring-up, and if that node
turns out to be unfit the fix is to name a different node — not to widen the
owner back to nobody.

| | |
|---|---|
| **Owning node** | `pmoves-5090` — Ryzen 9 9950XD / RTX 5090 32 GB / **192 GB RAM**, `deployment_class: private-mesh` |
| **Profile** | `pmoves/config/profiles/desktop-9950xd.yaml` (canonical). `workstation_5090.yaml` is a deprecated **alias of the same machine** — it says so in its own header. They are not two candidate nodes. |
| **Decision** | Operator, 2026-09-06: the 5090 owns the Danger Room. |
| **Vendor docs** | `PMOVES-Danger-infra/DEV-LOCAL.md` (local bare metal) · `PMOVES-Danger-infra/self-host.md` (GCP) |
| **Status of this runbook** | Written from the vendor docs and from probes run on B850. **Nothing here has been executed on the 5090.** Bring-up is an operator action. |

---

## 0. The blocker you must resolve before anything else

`tailscale status` reports **`pmoves-5090` as `windows`** (measured 2026-09-06,
online, alongside 25 other peers — so the field is being read, not defaulted).

`DEV-LOCAL.md` opens with:

> Note: Linux is required for developing on bare metal.

That is not a style preference. The three prerequisites are Linux **kernel**
features with no Windows equivalent:

| Requirement | Why it is Linux-only |
|---|---|
| Firecracker microVMs | Firecracker is a **KVM userspace VMM**. It opens `/dev/kvm`. No `/dev/kvm`, no sandboxes — full stop. |
| `sudo modprobe nbd nbds_max=64` | A Linux kernel module (network block device), used to attach template rootfs images. |
| `sudo sysctl -w vm.nr_hugepages=2048` | A Linux VM subsystem knob. |

So **Windows does not host the Danger Room.** A Linux environment *on* the 5090
might. That environment is either:

- **WSL2** — real Linux kernel, needs *nested* virtualization for `/dev/kvm`,
  and its default kernel historically ships **without `nbd`**; or
- **a full Hyper-V Linux VM** with `ExposeVirtualizationExtensions` on; or
- **a bare-metal Linux install / dual-boot** on the 5090.

**Do not guess which.** Run the probe.

### Step 0 — probe the node (read-only, provisions nothing)

Run **on the 5090**, in this order:

```powershell
# 1. Windows host half — run in an ELEVATED PowerShell.
#    Unelevated, the optional-feature checks return COULD-NOT-MEASURE.
powershell -ExecutionPolicy Bypass -File pmoves\scripts\probe_danger_room_host.ps1
```

```bash
# 2. Linux half — run INSIDE the WSL2 distro / VM the first half identified.
wsl -d <distro> -- bash pmoves/scripts/probe_danger_room_host.sh
# or, on a native-Linux candidate:
make -C pmoves sandbox-host-probe
```

Each item prints **PASS / FAIL / COULD-NOT-MEASURE**.

> **COULD-NOT-MEASURE is not a pass.** It means no reading was obtained — the
> tool was absent, permission was denied, or the interface did not exist. In
> the overall verdict it *outranks* FAIL, because an incomplete reading must
> never be reported as a complete one. The `.ps1` marks nested virtualization
> could-not-measure **by construction**: the decisive test is `/dev/kvm` inside
> the guest, and Windows cannot answer it.

Exit codes: `0` clean · `1` findings · `3` could-not-measure.

> **`make` cannot carry these codes.** GNU make exits **2** for any recipe
> failure. Measured with a control: recipes exiting 1 and 3 both make `make`
> exit 2, while the script run directly returns 3. The targets print the real
> code, but anything that *branches* on it must call the script:
> ```bash
> bash pmoves/scripts/probe_danger_room_host.sh; echo "exit=$?"
> ```

The probe was self-tested on B850, which returned **16 PASS / 4 FAIL / 1
COULD-NOT-MEASURE** — it discriminates rather than emitting one uniform
verdict. Its B850 findings (5 GiB available RAM against a 32 GiB requirement,
137 GiB free disk against 150 GiB, `:3002` already occupied) are themselves
independent support for moving the Danger Room off B850.

---

## 1. Requirements

Recorded here so the owning node can size the job before starting, rather than
discovering it at step 7.

| Resource | Requirement | Where it comes from |
|---|---|---|
| OS | **Linux** (native, VM, or WSL2 with nested virt) | `DEV-LOCAL.md` header |
| Arch | **x86_64** | the public kernel + firecracker downloads (steps 3, 7) |
| `/dev/kvm` | present **and** read-writable by the running user | Firecracker is a KVM VMM |
| `nbd` module | loadable, `nbds_max=64` | `DEV-LOCAL.md` step 1 |
| Huge pages | `vm.nr_hugepages=2048` → **4 GiB reserved** before any sandbox exists | `DEV-LOCAL.md` step 2 |
| Free RAM | **≥ 32 GiB** — nine infra services + three E2B services + 4 GiB hugepages + microVMs | derived from steps 2 and 4 |
| Free disk | **≥ 150 GiB** — public kernels, firecracker builds, template rootfs, Go build cache, nine containers | derived from steps 3, 4, 7, 12 |
| Toolchain | **Go**, Docker (daemon reachable), make, git | steps 6, 8, 9, 10, 11 are Go builds |

The RAM and disk numbers are **derived**, not quoted from the vendor doc —
`DEV-LOCAL.md` states no figures. Treat them as the floor at which this is not
a fight, not as a vendor guarantee.

> **The 5090's 192 GB is not what a WSL2 guest gets.** A WSL2 guest is capped by
> `%USERPROFILE%\.wslconfig`; with no explicit `memory=` it takes a fraction of
> host RAM. The Linux half reports the guest's real `MemTotal` — read that, not
> the profile.

### `arch:` is inferred, not declared

No node profile in this repo declares `arch:` — **0 of 18** (positive control:
14 of 18 declare `deployment_class:`, so the check works). x86_64 for the 5090
is an inference from the CPU model string "Ryzen 9 9950XD". The probe prints
`uname -m` / `PROCESSOR_ARCHITECTURE` so the placement decision rests on a
reading instead. See §5.

---

## 2. Bring-up — `DEV-LOCAL.md`, verbatim, with the traps annotated

**This is an operator action on `pmoves-5090`.** It is not automated here and
must not be run from another node.

Run from the `PMOVES-Danger-infra` checkout, inside the Linux environment:

```bash
sudo modprobe nbd nbds_max=64                 # 1
sudo sysctl -w vm.nr_hugepages=2048           # 2   reserves 4 GiB
make download-public-kernels                  # 3
make local-infra                              # 4   nine services, see below
cd packages/db        && make migrate-local   # 5
cd packages/envd      && make build-debug     # 6   embedded in templates
make download-public-firecrackers             # 7
cd packages/local-dev && go run seed-local-database.go   # 8  mints the dev user/team/token
cd packages/api           && make run-local   # 9   :3000
cd packages/orchestrator  && make run-local   # 10  :5008 (+ template-manager)
cd packages/client-proxy  && make run-local   # 11  :3002
cd packages/shared/script && make local-build-base-template  # 12
```

Traps, in the order you will hit them:

1. **Step 1 — `nbds_max` is set at insert time only.** If `nbd` is already
   loaded with a smaller value, `modprobe` will *not* raise it. You need
   `sudo rmmod nbd && sudo modprobe nbd nbds_max=64`. The probe reads the live
   value from `/sys/module/nbd/parameters/nbds_max` and says so.
2. **Step 1 on WSL2 — `nbd` may simply not exist.** The stock WSL2 kernel has
   historically shipped without it, which forces a custom WSL2 kernel or a full
   VM. The probe distinguishes "absent" from "unmeasurable" by retrying the
   same `modprobe --dry-run` against `loop` as a control.
3. **Step 2 is not persistent.** `sysctl -w` is lost on reboot. Persist it in
   `/etc/sysctl.d/` once the node is committed to the role.
4. **Steps 9–11 are three long-running foreground processes.** Three terminals,
   or a supervisor. They are not daemonised for you.
5. **Step 8 mints the local dev credentials.** Its output is where the
   `selfhost-local` client variables come from (§4). It is a *local* seed, not
   a production credential — but it is still a credential: do not paste it into
   a PR, a log, or a commit.

### What `make local-infra` starts (step 4)

`clickhouse`, `grafana`, `loki`, `memcached`, `mimir`, `otel`, `postgres`,
`redis`, `tempo` — nine services — **plus** the three E2B services you start by
hand in steps 9–11.

### Ports

| Port | Service | |
|---|---|---|
| **3000** | **e2b api** | ⚠️ **collision risk — see below** |
| **3002** | e2b client-proxy | occupied on B850 at probe time |
| **5008** | e2b orchestrator | |
| 5432 | postgres | |
| 8123 / 9000 | clickhouse http / native | |
| 6379 | redis | |
| 4317 / 4318 | otel collector grpc / http | |
| 30006 | vector | |
| 53000 | grafana | |

> ### ⚠️ Port 3000 is the loud one
> `:3000` is a default for a large amount of Node tooling and **has already
> collided once on this fleet**: a host `npx hf-mcp-server` took it, which is
> why PostgREST was moved to 3001. On a **Windows** host this is worse than
> usual, because WSL2 relays listeners through `localhost` — a *host* process on
> `:3000` conflicts with the *guest's* e2b api. The probe checks `:3000` on both
> sides for exactly this reason.
>
> If you move the api off 3000, **`E2B_API_URL` must move with it** or every
> client will talk to whatever else answers there.

---

## 3. The three deployment modes — do not generalise from one page

There are three E2B deployments and they take three **different** credential
sets. Reading one vendor page and applying it to another mode produced two
wrong wirings in a row on this lane. `pmoves/scripts/e2b_mode.sh` is the single
place that encodes the difference; `E2B_MODE` selects.

| Mode | Required | Source |
|---|---|---|
| `cloud` | `E2B_API_KEY` (`e2b_` + 40 hex) | e2b.dev docs |
| `selfhost-gcp` | `E2B_ACCESS_TOKEN` (`sk_e2b_` + 32 hex) **+ `E2B_DOMAIN`** | `PMOVES-Danger-infra/self-host.md` |
| `selfhost-local` | `E2B_API_KEY` + `E2B_ACCESS_TOKEN` + `E2B_API_URL` + **`E2B_DEBUG=true`**, and **no `E2B_DOMAIN`** | `PMOVES-Danger-infra/DEV-LOCAL.md` |

Select explicitly; the default is `selfhost-local` (operator decision
2026-09-06):

```bash
make -C pmoves sandbox-mode                          # what am I pointed at?
make -C pmoves sandbox-preflight                     # selfhost-local (default)
make -C pmoves sandbox-preflight E2B_MODE=cloud
make -C pmoves sandbox-preflight E2B_MODE=selfhost-gcp
make -C pmoves sandbox-preflight E2B_MODE=auto       # infer from what is set
```

---

## 4. Client configuration for `selfhost-local`

Set these on the machine running the **client** (the agent), pointing at the
5090's control plane. Values come from `DEV-LOCAL.md`'s dotenv block and from
step 8's seed output.

| Variable | Role | Notes |
|---|---|---|
| `E2B_API_KEY` | credential | funnel-managed; registered in `pmoves/tools/chit_manifest_register.py`, delivered to `env.tier-agent` |
| `E2B_ACCESS_TOKEN` | credential | same |
| `E2B_API_URL` | routing | `http://localhost:3000` locally; the 5090's reachable address from another node |
| `E2B_ENVD_API_URL` | routing | `http://localhost:3002` — declared by the vendor doc; see the caveat below |
| **`E2B_DEBUG=true`** | routing | **required**, see below |
| `E2B_DOMAIN` | **leave EMPTY** | GCP-only, see below |

**`E2B_DEBUG=true` is required and the vendor dotenv block does not say so.**
The pinned e2b python SDK (2.6.4) only returns `localhost:{port}` hosts when
debug is set (`e2b/sandbox/main.py:198`) and picks `http://` over `https://` off
the same flag (`:49`). Without it the SDK builds
`https://49983-<sandbox-id>.e2b.app` and never reaches your cluster — it fails
by silently talking to the wrong place. Mode selection exports it for you.

**`E2B_ENVD_API_URL` has no consumer at our pins.** Grep counts, with a positive
control alongside: in the SDK monorepo `E2B_API_KEY` matches 24 files,
`E2B_DOMAIN` 17, `E2B_ACCESS_TOKEN` 10, and `E2B_ENVD_API_URL` **0**. In
`PMOVES-Danger-infra` it matches exactly one file — `DEV-LOCAL.md` itself. The
python SDK derives the envd URL from debug + host and targets
`localhost:49983`, **not** the client-proxy `:3002` the doc names. Set it for
parity with the vendor doc and any JS/CLI client; do not expect the python path
to honour it, and do not treat setting it as having wired envd.

**`E2B_DOMAIN` belongs to the GCP path, not this one.** It is
`self-host.md`'s variable. The SDK defaults it to `e2b.app`, so setting it
against a local stack **misroutes every sandbox host the SDK builds**.
`e2b_mode.sh` warns when it is set under `selfhost-local`.

### Why shape, not presence

`[ -n "$VAR" ]` passes a **truncated** secret. That is exactly how this lane
stalled: the `E2B_API_KEY` reaching B850 was **42 characters and missing its
`e2b_` prefix** — *longer* than any minimum-length floor, so every presence
check and every `min_length` gate passed it, and only the provider rejected it,
deep inside a provisioning call. `e2b_mode.sh` validates prefix + charset +
per-mode length instead. Run `make -C pmoves sandbox-preflight` and believe it.

Nothing in these scripts prints a credential value — names, lengths, prefixes
and verdicts only. The `set +x` guards are deliberate: under `bash -x`, xtrace
expands `[ -n "$E2B_API_KEY" ]` and prints the secret. That has happened on this
fleet before.

---

## 5. Two profile gaps this runbook ran into

**No profile declares `os:`.** 0 of 18 (control: 14 of 18 declare
`deployment_class:`). The 5090 being Windows — the single fact that reshapes
this entire runbook — was learned from `tailscale status`, not from
`desktop-9950xd.yaml`, which is the first place a placement decision looks. A
proposal is in §5 of the PR discussion; unknown values must stay **unset**, per
the profile format's own rule that *unset means unset*.

**Three nodes appear in `fleet-status` with no profile at all:** `kiloclaw`,
`pmoveseldermelchor`, `pmoves-nano-1`. Their specs are not fabricated here.
(Also measured: the Tailscale peer named `Elder-Melchor` reports OS `windows`,
not `linux` — worth confirming against whichever device `pmoveseldermelchor`
actually is before anyone places work on it.)

---

## 6. Known Road

```
make -C pmoves sandbox-runbook       # owning node + every path in this lane
make -C pmoves sandbox-host-probe    # is THIS node fit? (read-only)
make -C pmoves sandbox-mode          # which mode am I resolved to?
make -C pmoves sandbox-preflight     # CLI runnable + selected mode's creds well-shaped
make -C pmoves sandbox-smoke         # end-to-end: provision -> exec -> tear down
make -C pmoves sandbox-create        # provision one, print its ID
make -C pmoves sandbox-list
make -C pmoves sandbox-info  SBX=<id>
make -C pmoves sandbox-exec  SBX=<id> CMD='echo hi'
make -C pmoves sandbox-kill  SBX=<id>
```

Entrypoint doc: `.claude/skills/agent-sandbox/SKILL.md`.
Mode resolver: `pmoves/scripts/e2b_mode.sh`.

---

## 7. What has *not* been done

Stated plainly so nobody reads this page as a completed bring-up:

- **The stack has not been brought up anywhere.** No `make local-infra`, no
  Terraform, no Packer, no gcloud. This lane was wiring, probing and
  documentation only.
- **Nothing has been run on the 5090.** Both probe halves were written *for*
  that node, by a node that cannot reach into it. The `.ps1` has never
  executed — there is no PowerShell on B850 — so **treat its first run on the
  5090 as its syntax test**. Its brace/paren/bracket nesting was checked
  statically.
- **`selfhost-local` has never been reached.** `sandbox-preflight` on B850
  fails shape validation (malformed `E2B_API_KEY`, unset `E2B_ACCESS_TOKEN`,
  unset `E2B_API_URL`), so no client has ever spoken to a local control plane.
  The mode is wired and validated; it is not *proven*.
- **No credential was minted, rotated, revoked or set.** Where proving
  something would have required a live mutation, the answer recorded is
  COULD-NOT-MEASURE — which is an acceptable outcome, and not a pass.
