---
name: 4090:verify
description: >
  Verify the 4090 node's W0 substrate artifacts landed correctly on main.
  Checks: node-4090-probe SKILL.md has no BLOCKED notices,
  json-to-profile.py has unifi_topology wired, TAC probe-wire is status:done.
  Run after any W0 PR merge. For secrets health, use deploy:secrets-funnel.
---

# 4090:verify — W0 Substrate Artifact Check

Confirms the three W0 substrate deliverables are correctly on main after
a PR merge. Scoped to artifact state only — secrets funnel is a separate
concern covered by `deploy:secrets-funnel`.

## Run

```bash
PASS=0; FAIL=0

check() {
  local label="$1"; shift
  if eval "$@" >/dev/null 2>&1; then
    echo "✓ $label"; PASS=$((PASS+1))
  else
    echo "✗ $label"; FAIL=$((FAIL+1))
  fi
}

# 1. node-4090-probe SKILL.md: no BLOCKED notice
BLOCKED=$(grep -c "BLOCKED" .claude/skills/node-4090-probe/SKILL.md 2>/dev/null || echo "99")
check "SKILL.md: no BLOCKED notice" "[ \"$BLOCKED\" = \"0\" ]"

# 2. json-to-profile.py: unifi_topology wired (PR #1599)
check "json-to-profile.py: unifi_topology wired" \
  "grep -q 'unifi_topology' deploy/provision/json-to-profile.py"

# 3. TAC: probe-wire status=done (PR #1599)
check "TAC: probe-wire status=done" \
  "grep -A8 'probe-wire' pmoves/configs/tac_trees/node-4090-laptop.tac.yaml | grep -q 'status: done'"

echo ""
echo "W0 substrate: $PASS passed, $FAIL failed"
[ "$FAIL" = "0" ] && echo "ALL CHECKS PASSED" || echo "ACTION REQUIRED — see ✗ items above"
```

## Expected Output

```text
✓ SKILL.md: no BLOCKED notice
✓ json-to-profile.py: unifi_topology wired
✓ TAC: probe-wire status=done

W0 substrate: 3 passed, 0 failed
ALL CHECKS PASSED
```

## Fix Recipes

| Failure | Fix |
|---------|-----|
| SKILL.md BLOCKED | `git checkout main && git pull origin main` — fix landed in PR #1599 |
| `unifi_topology` missing | Pull main — wired in PR #1599 |
| TAC probe-wire not done | Pull main — updated in PR #1599 |

## Notes

- Run from repo root on `main` (or any branch including PR #1599+)
- W0 chain: PR #1591 (ghost detector) → #1588 (unifi probe) → #1486 + #1599 (json-to-profile + completion)
- For secrets health: use `deploy:secrets-funnel` or `make -C pmoves secrets-audit`
- See `node-4090-probe` for the hardware probe workflow
- See `node-4090-sitrep` for quick git/GPU/NATS health
