# Spark A0 Stand-Up — Measured State & Operator Runbook (2026-10-07)

> **✅ EXECUTED 2026-10-07 ~08:05–09:05 EDT — all phases verified. Read §0 for the final state; the original blockers/runbook below are kept as the historical record.**

## §0 FINAL STATE (verified live, cross-node)

| Item | Final state |
|---|---|
| Root disk | **229G free / 74% used** (was 0 free / 100%) — reclaimed 8.75G docker build cache + 8G clmvenv + 621M apt + **211G old ollama models (deleted after cutover verification)** |
| Ollama | **Serving from the 4TB drive**: `/media/powerfulmoves/pmoves-archive/ollama/models` (261.6G, 110 files, rsync + double delta-sync verified, hardlinks preserved). Roster (12 models incl. qwen3.5:35b-a3b-q8_0), `/v1/embeddings` (qwen3-embedding:8b), and `/api/generate` (qwen3:8b, HTTP 200 real completion) ALL verified from the new path |
| Reboot-proofing | fstab entry (UUID dc97f524-…) + systemd drop-in `pmoves-models.conf` with `RequiresMountsFor` + ACL `u:ollama:x` on `/media/powerfulmoves` (the traverse fix for crash-loop counter 34) |
| Tailnet exposure | `tailscale serve` tailnet-only: **`/a0`→8080 (A0 supervisor), `/a0-mcp`→8081, `/ollama`→11434** — TLS probes 200/200/200 on-node AND **cross-node from sidecar: healthz 200 (NATS+JetStream connected), embeddings returned real vectors** |
| Security cleanup | Stale public funnel (dead backend :38457) turned OFF; stale `/` serve path removed. Serve table = exactly the three clean paths |
| Claim lane | CLAIM 08:05Z → AMEND 08:42Z → RELEASE (this row) in AGNOTE4482PHI.t1.md; sign-trail HMAC'd |
| Known remaining | 5082/5083 UI ports still down (orphaned `/opt/pmoves-main` worktree — fresh clone + `make -C pmoves up-agents` is the documented path, now unblocked by disk space); `/opt/pmoves-main` orphaned worktree not yet re-cloned; clm-eval-spark.yml encoder port still says 8090-vLLM (needs the Ollama-11434 patch + clm-serve wiring verification before next dispatch — qwen3-embedding vs Qwen3-8B-base embedding-space compatibility caveat applies) |
| Recovery incident | During cutover, ollama crash-looped (mkdir permission denied — ollama user couldn't traverse /media/powerfulmoves). Fixed with targeted ACL x-bit; total inference downtime ~6 min |

---

**Author:** agent0-sidecar (A0 digital-twin) · **Channel proven:** Windows CLI host → `ssh pmoves@100.89.7.106` (Tailscale, fix-path-B user) · **Claim row:** CLAIM 2026-10-07T08:05Z in AGNOTE4482PHI.t1.md (TTL 24h)

## 1. What stands TODAY (verified live, 2026-10-07 ~08:00–08:20 EDT)

| Component | State | Evidence |
|---|---|---|
| **A0 supervisor** | ✅ ALIVE | `GET :8080/healthz` → 200: `run_ui.py --dockerized`, pid 125, **NATS+JetStream connected**, controller started |
| A0 MCP facade | ✅ alive, localhost-bound | 8081 listening on 127.0.0.1 only |
| Ollama | ✅ alive — DO NOT TOUCH | 12 models incl. **qwen3.5:35b-a3b-q8_0 (38.7G P0 brain)**, qwen2.5-coder:32b, embed roster; llama-server actively serving (9.7G GPU @ 96% util) |
| Notebook / TensorZero | ✅ alive | 5055 → 200; 3030 → 404-at-root (up) |
| 5082/5083 UI ports | ❌ DEAD | connection refused; OBSERVATION_LINKS.md reflects a `make showtime` from a checkout that is now orphaned |
| Cross-node reachability | ❌ BLOCKED | all services 127.0.0.1-bound (the known fleet blocker, unchanged) |
| Tailscale funnel | ⚠️ STALE | public URL `pmoves-spark.tailcad9b4.ts.net` has funnel ON → backend 127.0.0.1:38457 has **no listener and no response** — dead config, public hostname answers nothing; cleanup recommended |
| /opt/pmoves-main | ❌ orphaned | worktree `.git` → `/home/powerfulmoves/PMOVES.AI/.git/worktrees/pmoves-main` (target gone); compose bring-up from it impossible |

## 2. Two hard blockers (both measured)

### Blocker A — root disk 100% full
`/` = 916G total, 870G used, **0 available**. `scp` to Spark fails on ENOSPC; no image pull, no log write, no compose up can proceed. Reclaimables: `/tmp/clmvenv` **8.0G** (CLM-eval venv; usage-checked — no process cwd or maps reference it → safe to remove), apt cache 621M, container json logs, docker build cache (sizes need root to enumerate; docker layers/ollama blobs are the unseen bulk).

### Blocker B — sudo password mismatch
`pmoves` ∈ sudo group, but the ROOT_PASSWORD secret alias was **rejected twice** on a clean TTY (2 of 3 attempts used, then circuit-breaker stop — no guessing, no third try). Either the alias maps to a different node or the cmd-layer channel mangles special characters. Operator: supply the correct secret alias or run the root batch directly.

## 3. Operator root batch (~10 min, zero service impact — Ollama untouched)

```bash
ssh pmoves@100.89.7.106        # or Spark console
sudo -i
# --- 1. reclaim ~9G fast ---
rm -rf /tmp/clmvenv            # usage-checked 2026-10-07; re-verify: lsof +D /tmp/clmvenv 2>/dev/null
apt-get clean
journalctl --vacuum-size=100M
docker builder prune -f && docker image prune -f   # dangling only — NO volume prune, ever
df -h /                        # confirm headroom
# --- 2. one-time tailnet exposure (sanctioned ts_serve pattern; no ACL change) ---
tailscale set --operator=pmoves
sudo -u pmoves tailscale serve --bg --set-path=/a0     http://127.0.0.1:8080
sudo -u pmoves tailscale serve --bg --set-path=/a0-mcp http://127.0.0.1:8081
sudo -u pmoves tailscale serve --bg --set-path=/ollama http://127.0.0.1:11434
# --- 3. stale funnel cleanup (dead backend; closes a public hostname) ---
tailscale funnel off
# --- 4. verify ---
tailscale serve status
curl -s http://localhost:8080/healthz
```

**Security note on serve paths:** these expose tailnet-only endpoints with auto-TLS. `/ollama` is convenient for the CLM eval lane but allows any tailnet device to run inference — fine inside tag:pmoves, revisit if the tailnet widens.

## 4. Post-unblock sequence (sidecar drives end-to-end once sudo works)
1. Disk verified free → I rerun the staged heal script (`C:\Users\russe\spark_heal.sh` on the Windows host) for the deeper clean: builder prune, dangling images, >50M log truncation, docker/ollama sizing
2. Serve additions + funnel-off verified from sidecar: `curl https://pmoves-spark.tailcad9b4.ts.net/a0/healthz` → 200
3. Fresh clone decision for `/opt/pmoves-main` (393M) + `make -C pmoves up-agents` to restore the 5082/5083 UI era — only after headroom
4. **CLM eval lane** (the reason Spark A0 matters): `scripts/spark_clm_eval.sh` per `plans/CLM_EVAL_SPEC_2026-10-05.md` — vLLM Qwen3-8B pooling :8090 + clm-serve :8700 ≈ 25G on 128G unified — fits. Baselines: TypeSafe Jev (live key) + AgentJev-0.6B ONNX (already benchmarked here at 129ms/decision)
5. Sign-trail + register RELEASE

## 5. Variance note — what "stand up" meant here
Spark A0 was never fully down: the **supervisor has been alive the whole time** (NATS+JetStream connected) — what's dead is its reachability (localhost-bound), its UI ports (5082/5083, orphaned checkout), and any mutation capacity (100% disk). Standing it up = heal disk + expose via ts_serve + (optionally) fresh-clone the compose stack. All measured; nothing touched; Ollama serving load (GB10 @ 96%) left alone.

*Channel: Windows CLI → ssh pmoves@100.89.7.106 (Tailscale 100.89.7.106, aarch64, up 3d16h). Runbook by a0-sidecar twin, 2026-10-07.*