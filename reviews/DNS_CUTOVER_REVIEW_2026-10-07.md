# persona.pmoves.ai DNS cutover — decision review (2026-10-07)

**Author:** agent0-sidecar (A0 digital-twin) · **Mode:** Control-style review, read-only. **No DNS or firewall change was made.**
**Trigger:** operator 2026-10-07: "lets review for dns cut over cloudflare is also on composio as well as hostinger".

---

## 1. Measured state (all probes 2026-10-07 unless noted)

### DNS authority
- `NS pmoves.ai` → **dara / alex.ns.cloudflare.com** — the zone is **Cloudflare-authoritative**. Hostinger is **not** in the DNS path (it hosts the current website + the KVMs, and holds the `www` CNAME target `www.pmoves.ai.cdn.hstgr.net`). Cutover = one Cloudflare zone, full stop.
- `persona.pmoves.ai` → **NXDOMAIN (status 3)** — unchanged, still the calendar's hard blocker.
- `auth`, `chit` → NXDOMAIN. `www`, apex, `ftp` → resolve (Cloudflare-proxied, Hostinger origin). `id`/`relay` → DNS-only A → 167.88.38.57 (RustDesk on kvm2, live since 2026-09-15).
- Zone inventory read live via CF API: **12 records**, none of the record-bank fleet names exist yet.

### Credentials / write paths
| Path | State (measured) |
|---|---|
| `CLOUDFLARE_API_TOKEN` (env.shared, len 53) | **LIVE for reads** — listed the zone (`pmoves.ai`, id `2637f85762187500b640e32a2d67db02`, active) and all 12 records. Write scope (**Zone:DNS:Edit**) **untested** — needs a GO-approved scratch TXT create+delete or the real create attempt |
| `CLOUDFLARE_DNS_API_TOKEN` (env.shared) | **EMPTY (len 0)** — the 2026-08-18 finding still true → Traefik ACME DNS-01 (`certresolver=cf`) cannot issue certs anywhere this env reaches |
| Composio Cloudflare connection | **BROKEN** — `CLOUDFLARE_LIST_ZONES` → HTTP 403, code 9109 "Invalid access token". Operator reconnect in dashboard.composio.dev needed if composio is to be the mutation path |
| `HOSTINGER_API_KEY` (len 48) | present — relevant only for the Direct path (cloud-firewall port opening on the KVM) |
| `CLOUDFLARE_TUNNEL_TOKEN` | **no key exists in env.shared** — must be minted (Zero Trust dashboard) for the Tunnel path |

Note: the 08-21 register row proves the fleet has already run a working edge — 5090 issued real Let's Encrypt certs for auth/health/wealth.pmoves.ai via ACME DNS-01 (#2658/#2650), i.e. a live DNS token existed **on that node's env**, even though the sidecar/env.shared copy is empty. Verify before reusing.

### Ingress candidates
| Candidate | 80/443 today | Notes |
|---|---|---|
| kvm2 — IP per id/relay records: 167.88.38.57 | **closed** | RustDesk ports only |
| kvm2 — IP per `HOSTINGER_KVM2_IP`: 31.97.42.207 | **closed** | **IP DISCREPANCY** — env and live DNS records name two different IPs for kvm2. Confirm which is current before pointing any A record |
| Spark (GB10) | no public ingress by design | tailnet-only serve (today's standup) |
| 5090 / z890 | home nodes | record bank: use Tunnel, not Direct |

**Conclusion: no public ingress exists anywhere in the fleet today.** DNS is necessary-but-not-sufficient, exactly as `PMOVES_AI_DNS_RECORD_BANK.md` predicted.

---

## 2. The two viable designs (record bank §matrix, still canonical)

### Option T — Cloudflare Tunnel (RECOMMENDED for first cutover)
- **Record:** `CNAME persona.pmoves.ai → <tunnel-id>.cfargotunnel.com`, **proxied ON**.
- **Origin:** cloudflared (compose profile `cloudflare`, `docker-compose.core.yml:1189`) on the 5090 or z890 → Traefik (`pmoves-traefik`, routes `Host(persona.pmoves.ai)` — the persona-room labels are already on main) → persona-room :8080.
- **Needs:** mint `CLOUDFLARE_TUNNEL_TOKEN` (Zero Trust → Networks → Tunnels) → funnel via `make secrets-rotate KEY=CLOUDFLARE_TUNNEL_TOKEN` → `up-persona` on the chosen node → CNAME create.
- **Pros:** no firewall ports, no empty-token blocker, no residential-IP exposure, TLS at Cloudflare edge (no ACME dependency). Fastest path to a **serving** persona.pmoves.ai. Same pass can add `chit.pmoves.ai` (the chit-tour handoff explicitly asks to batch both).
- **Cons:** origin availability tied to a home node; add `ha` replica later.

### Option D — Direct on kvm2 (durable, more steps)
- **Record:** `A persona.pmoves.ai → <kvm2 public IP>`, **proxied OFF** (Traefik terminates TLS via ACME).
- **Needs:** resolve the kvm2 **IP discrepancy** → Hostinger cloud-firewall open 80/443 (API key present) → mint + funnel `CLOUDFLARE_DNS_API_TOKEN` (Zone:DNS:Edit + Zone:Zone:Read per the compose comment) → provision repo+docker on kvm2 → `make -C pmoves up-edge` (first-ever fleet edge on a KVM) → `up-persona` → A record.
- **Pros:** the sanctioned always-on public edge; carries all seven record-bank names long-term.
- **Cons:** longest critical path; blocked today on the empty DNS token + unbuilt KVM edge.

### Mutation paths for the record itself (on GO)
1. **CF API direct** with the live env token — works for reads today; write scope untested (one scratch TXT create+delete proves it cleanly).
2. **Composio toolkit** (`CLOUDFLARE_CREATE_DNS_RECORD`, args `zone_id`/`type`/`name`/`content`) — **blocked until the operator reconnects the Cloudflare connection** (403 9109).
3. **Dashboard** — always available fallback.

---

## 3. Recommendation

**Option T (Tunnel) first, batch `persona` + `chit` CNAMEs in one pass, then migrate to Option D when the kvm2 edge is provisioned** (CNAME→A swap is a one-record change). This unblocks the content calendar this week without waiting on the DNS-token funnel or KVM bring-up.

## 4. Not yet run (GO-gated)
- CF token write-permission proof (scratch TXT create+delete).
- Any record create/update/delete.
- Any tunnel creation, firewall change, or container bring-up.
- kvm2 IP discrepancy resolution (operator or Hostinger API read on GO).

*Sources: live DoH + CF API reads (this review), `pmoves/docs/operations/PMOVES_AI_DNS_RECORD_BANK.md`, `docs/handoffs/persona-room-public-edge.md`, `docs/handoffs/chit-tour-public-edge.md`, `docs/operations/PERSONA_AND_VOICE_GOLIVE_RUNBOOK.md`, `docs/operations/FLEET_APP_HOSTING_SECURITY.md`, `docs/operations/RUSTDESK_KVM2_CLIENT_SETUP.md`, `docker-compose.traefik.yml` + `docker-compose.persona.yml` headers, AGNOTE4482PHI.t1 rows 2026-08-18/08-21/08-27, `reviews/SPARK_A0_STANDUP_RUNBOOK_2026-10-07.md`.*
