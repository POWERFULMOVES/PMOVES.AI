#!/usr/bin/env bash
# run_static.sh — Tier 1 static validation for the Wave 0 gap-fill scaffold.
#
# Scope: lint markdown frontmatter, syntax-check scripts, verify cross-link
# anchors and plan checklist count. NO services required.
#
# Plan: docs/superpowers/plans/2026-05-15-pmoves-gap-fill-roadmap.md
# Validation plan: /home/pmoves-knuckles/.claude/plans/greedy-snuggling-treehouse.md

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
FAILURES=()

ok()   { echo "  ✅ $*"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $*"; FAIL=$((FAIL+1)); FAILURES+=("$*"); }

section() { echo; echo "── $* ──"; }

# Path to python for YAML parsing (use system python3; PyYAML required)
PY=python3

# ---- 1. Skill frontmatter ----
section "Skill SKILL.md frontmatter (8 files)"
SKILL_DIRS=(
  .claude/skills/fork-repository
  .claude/skills/agent-sandbox
  .claude/skills/claude-d3js
  .claude/skills/pmoves-mesh-preflight
  .claude/skills/pmoves-nats-subject-audit
  .claude/skills/pmoves-living-docs-refresh
  .claude/skills/pmoves-submodule-fleet
  .claude/skills/pmoves-chit-sign
)
for d in "${SKILL_DIRS[@]}"; do
  f="$d/SKILL.md"
  if [[ ! -f "$f" ]]; then bad "missing $f"; continue; fi
  result=$($PY - "$f" <<'PYEOF' 2>&1
import sys, yaml, re
p = sys.argv[1]
try:
    text = open(p).read()
    m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not m:
        print("NO-FRONTMATTER"); sys.exit(1)
    fm = yaml.safe_load(m.group(1))
    missing = [k for k in ("name", "description") if k not in fm]
    if missing:
        print(f"MISSING-KEYS:{','.join(missing)}"); sys.exit(1)
    print(f"OK name={fm['name']}")
except yaml.YAMLError as e:
    print(f"YAML-ERROR:{e}"); sys.exit(1)
except Exception as e:
    print(f"ERROR:{e}"); sys.exit(1)
PYEOF
)
  if [[ "$result" == OK* ]]; then ok "$f ($result)"; else bad "$f → $result"; fi
done

# ---- 2. Agent frontmatter ----
section "Subagent .md frontmatter (5 files)"
AGENT_FILES=(
  .claude/agents/archon-qa-agent.md
  .claude/agents/chit-compliance-reviewer.md
  .claude/agents/chit-pr-audit-agent.md
  .claude/agents/claim-collision-agent.md
  .claude/agents/nats-subject-auditor.md
)
for f in "${AGENT_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then bad "missing $f"; continue; fi
  result=$($PY - "$f" <<'PYEOF' 2>&1
import sys, yaml, re
p = sys.argv[1]
text = open(p).read()
m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
if not m:
    print("NO-FRONTMATTER"); sys.exit(1)
fm = yaml.safe_load(m.group(1))
missing = [k for k in ("name", "description", "tools") if k not in fm]
if missing:
    print(f"MISSING-KEYS:{','.join(missing)}"); sys.exit(1)
print(f"OK name={fm['name']}")
PYEOF
)
  if [[ "$result" == OK* ]]; then ok "$f ($result)"; else bad "$f → $result"; fi
done

# ---- 3. Slash command frontmatter ----
section "Slash command .md frontmatter (3 files)"
CMD_FILES=(
  .claude/commands/archon/mint-agent.md
  .claude/commands/archon/mint-skill.md
  .claude/commands/archon/creator-onboard.md
)
for f in "${CMD_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then bad "missing $f"; continue; fi
  result=$($PY - "$f" <<'PYEOF' 2>&1
import sys, yaml, re
p = sys.argv[1]
text = open(p).read()
m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
if not m:
    print("NO-FRONTMATTER"); sys.exit(1)
fm = yaml.safe_load(m.group(1))
if "description" not in fm:
    print("MISSING-KEY:description"); sys.exit(1)
print("OK")
PYEOF
)
  if [[ "$result" == OK* ]]; then ok "$f"; else bad "$f → $result"; fi
done

# ---- 4. Shell script syntax ----
section "Shell script syntax (bash -n)"
SHELL_SCRIPTS=(
  .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh
  .claude/skills/pmoves-living-docs-refresh/scripts/refresh.sh
  .claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh
  .claude/hooks/governance/signoff-gate.sh
  .claude/hooks/posttool-format/python-format.sh
  .claude/hooks/posttool-format/ui-lint.sh
  .claude/hooks/session-env-check.sh
)
for f in "${SHELL_SCRIPTS[@]}"; do
  if [[ ! -f "$f" ]]; then bad "missing $f"; continue; fi
  if bash -n "$f" 2>/dev/null; then ok "$f"; else bad "$f → bash -n failed"; fi
done

# ---- 5. Python syntax ----
section "Python file syntax (py_compile)"
PY_FILES=(
  .claude/hooks/governance/known-roads-enforcer.py
  .claude/hooks/governance/claim-collision-pre.py
  .claude/skills/pmoves-nats-subject-audit/scripts/audit.py
  pmoves-nats-mcp/nats_mcp/__init__.py
  pmoves-nats-mcp/nats_mcp/server.py
  pmoves-nats-mcp/nats_mcp/tools.py
)
for f in "${PY_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then bad "missing $f"; continue; fi
  if $PY -m py_compile "$f" 2>/dev/null; then ok "$f"; else bad "$f → py_compile failed"; fi
done

# ---- 6. Executability ----
section "Script executable bits"
EXEC_SCRIPTS=(
  .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh
  .claude/skills/pmoves-living-docs-refresh/scripts/refresh.sh
  .claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh
  .claude/skills/pmoves-nats-subject-audit/scripts/audit.py
  .claude/hooks/governance/signoff-gate.sh
  .claude/hooks/governance/known-roads-enforcer.py
  .claude/hooks/governance/claim-collision-pre.py
  .claude/hooks/posttool-format/python-format.sh
  .claude/hooks/posttool-format/ui-lint.sh
)
for f in "${EXEC_SCRIPTS[@]}"; do
  if [[ -x "$f" ]]; then ok "$f executable"; else bad "$f not executable"; fi
done

# ---- 7. Cross-link anchors ----
section "Documentation cross-links"
if grep -q "Gap-fill artifacts (2026-05-15)" .claude/PATTERNS.md; then
  ok ".claude/PATTERNS.md has gap-fill section"
else
  bad ".claude/PATTERNS.md missing 'Gap-fill artifacts (2026-05-15)' anchor"
fi

PLAN_FILE=docs/superpowers/plans/2026-05-15-pmoves-gap-fill-roadmap.md
if [[ -f "$PLAN_FILE" ]]; then
  count=$(grep -c "^- \[ \]" "$PLAN_FILE" || echo 0)
  if [[ "$count" -ge 30 ]]; then
    ok "plan checklist count = $count (≥30)"
  else
    bad "plan checklist count = $count (expected ≥30)"
  fi
else
  bad "plan file missing: $PLAN_FILE"
fi

if grep -q "Activated (2026-05-15)" skills/README.md; then
  ok "skills/README.md status column updated"
else
  bad "skills/README.md missing 'Activated (2026-05-15)' status"
fi

# ---- 8. NATS MCP import-and-introspect ----
section "NATS MCP import-and-introspect"
UV=""
for candidate in "$HOME/snap/code-insiders/2398/.local/bin/uv" "$HOME/.local/bin/uv" "/usr/local/bin/uv" "$(command -v uv 2>/dev/null)"; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then UV="$candidate"; break; fi
done
if [[ -z "$UV" ]]; then
  bad "uv binary not found (tried snap-confined, ~/.local/bin, /usr/local/bin, PATH)"
else
  ok "uv found at $UV"
  out=$("$UV" run --project pmoves-nats-mcp --quiet python -c "from nats_mcp.server import app; from nats_mcp.tools import TOOLS, TOOL_HANDLERS; assert app.name=='pmoves-nats'; assert len(TOOLS)==2; assert set(TOOL_HANDLERS.keys())=={'nats_publish','nats_subscribe'}; print('OK')" 2>&1)
  if [[ "$out" == "OK" ]]; then
    ok "pmoves-nats MCP imports + 2 tools registered"
  else
    bad "pmoves-nats MCP introspect → $out"
  fi
fi

# ---- Summary ----
echo
echo "════════════════════════════════════════════════════════"
echo "Static validation: PASS=$PASS  FAIL=$FAIL"
echo "════════════════════════════════════════════════════════"
if [[ "$FAIL" -ne 0 ]]; then
  echo "Failures:"
  for msg in "${FAILURES[@]}"; do echo "  - $msg"; done
  exit 1
fi
exit 0
