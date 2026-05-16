# 4090 Handoff Fix Locations — 2026-05-16

From handoff report `reports/handoff_4090_claude_2026-05-14.md`. Actionable items documented for next session.

---

## 1. Z.AI Temperature Override (HIGH)

**Problem:** GLM-5-Turbo defaults to `temperature: 1.0` — too creative for coding tasks. Must override to 0.0-0.3.

**Fix Location:** Agent Zero provider config
- Check: `pmoves/services/agent-zero/` settings or `.a0proj/` for `zai_coding` provider
- In TensorZero function config: `pmoves/tensorzero/tensorzero.toml` — add `temperature = 0.1` to Z.AI variant
- In Agent Zero chat params: override via system prompt or provider config

**Blocked by:** Submodule init (all 50+ submodules empty in Docker container). Run on host:
```bash
cd /path/to/PMOVES.AI
git submodule update --init --recursive
```

---

## 2. Profile Naming Drift (LOW)

**Problem:** `apply_profile.sh` and Makefile default to `HOST=workstation_5090` but no matching profile exists.

**Actual profiles in `pmoves/config/profiles/`:**

| Profile ID | Hardware |
|---|---|
| `desktop-9950xd` | AMD 9950XD workstation |
| `intel-265kf-3090ti` | Intel 265KF + 3090 Ti |
| `laptop-4090` | Laptop with RTX 4090 |
| `jetson-orin-nano` | Jetson Orin Nano |
| `jetson-nano` | Jetson Nano |
| `esp32-sonatino` | ESP32 microcontroller |

**Mapping:**
- `workstation_5090` → likely `desktop-9950xd` (closest high-end desktop profile)
- The 5090 node should use `desktop-9950xd` or a new `desktop-5090` profile should be created

**Fix:** Update `pmoves/scripts/apply_profile.sh` and `Makefile` to use `desktop-9950xd` as default, or create a `desktop-5090` profile.

---

## 3. Submodule Init (CRITICAL)

All 50+ submodules have zero files on disk in Docker. Not dirty state — just never checked out.

```bash
cd /path/to/PMOVES.AI
git submodule update --init --recursive
```

Verification:
```bash
find PMOVES-ClawZ -type f | head -5  # Should show source files
find Pmoves-cipher -type f | head -5   # Should show TypeScript
```

---

## 4. ClaWZ Fork Sync (HIGH)

- Fork `main`: **1,092 commits behind** upstream `openclaw/openclaw`
- Fork has **6 PMOVES-specific commits ahead**
- Hardened branch is **12,438 behind** — effectively dead

**Action:**
1. Sync fork main to upstream (rebase or merge, preserve 6 commits)
2. Cut fresh hardened branch from synced main
3. Abandon old hardened branch

---

## 5. GLM-5V-Turbo Missing from SDK (MEDIUM)

`pmoves/providers/zai/sdk.py` MODELS dict missing `GLM-5V-Turbo` entry.
Blocked by submodule init — file is inside ClawZ submodule.

---

*Documented by SIDECAR-SPARK, 2026-05-16*
