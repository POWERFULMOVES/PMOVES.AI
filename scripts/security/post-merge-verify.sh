#!/usr/bin/env bash
# ============================================================================
# post-merge-verify.sh — Post-merge security hardening verification suite
# ============================================================================
# Verifies that merged security PRs are effective:
#   PR #1327 — Headscale ACL hardening
#   PR #1331 — Supabase RLS + pg_stats lockdown + anon→service_role migration
#   PR #1332 — CVE image version upgrades
#   PR #1333 — Data-tier service authentication (Qdrant, Neo4j, Meilisearch)
#
# Usage: ./scripts/security/post-merge-verify.sh
#   Exit 0 = all checks pass, Exit 1 = any failure
#   Services need NOT be running — unreachable checks print YELLOW warnings
# ============================================================================
set -euo pipefail

# -- Paths -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_CORE="$REPO_ROOT/pmoves/docker-compose.core.yml"
COMPOSE_N8N="$REPO_ROOT/pmoves/docker-compose.n8n.yml"
ACL_YAML="$REPO_ROOT/pmoves/config/headscale/acl.yaml"
CONFIG_YAML="$REPO_ROOT/pmoves/config/headscale/config.yaml"
ENV_DATA_EXAMPLE="$REPO_ROOT/pmoves/env.tier-data.example"
ENV_SUPA_EXAMPLE="$REPO_ROOT/pmoves/env.tier-supabase.example"

# -- Colors -------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# -- Counters -----------------------------------------------------------------
PASS=0
FAIL=0
WARN=0
TOTAL=0

# -- Helpers ------------------------------------------------------------------
pass_check() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); echo -e "  ${GREEN}PASS${NC} $1"; }
fail_check() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); echo -e "  ${RED}FAIL${NC} $1"; }
warn_check() { WARN=$((WARN + 1)); TOTAL=$((TOTAL + 1)); echo -e "  ${YELLOW}WARN${NC} $1"; }
section()    { echo -e "\n${CYAN}== $1 ==${NC}"; }

# Check if a TCP port is reachable (timeout 2s)
port_up() { timeout 2 bash -c "echo >/dev/tcp/localhost/$1" 2>/dev/null; }

# -- Source env files (conditionally) -----------------------------------------
for _envf in "$REPO_ROOT/pmoves/env.shared" "$REPO_ROOT/pmoves/env.tier-data" "$REPO_ROOT/pmoves/env.tier-supabase"; do
  [[ -f "$_envf" ]] && set -a && source "$_envf" && set +a
done

# ============================================================================
# 1. Supabase RLS Verification (PR #1331)
# ============================================================================
check_supabase_rls() {
  section "1. Supabase RLS — anon gets nothing, service_role gets data (PR #1331)"
  local tables=(conversations agent_configs vector_embeddings event_log agent_threads)

  if [[ -z "${SUPABASE_DB_URL_ANON:-}" ]]; then
    warn_check "SUPABASE_DB_URL_ANON not set — skipping RLS checks"
    return 0
  fi

  if ! psql "$SUPABASE_DB_URL_ANON" -c "SELECT 1" &>/dev/null; then
    warn_check "Supabase DB not reachable — skipping RLS checks"
    return 0
  fi

  for tbl in "${tables[@]}"; do
    # Anon: should return 0 rows or permission denied
    local anon_count
    anon_count=$(psql "$SUPABASE_DB_URL_ANON" -t -A -c "SELECT count(*) FROM pmoves_core.$tbl;" 2>/dev/null || echo "ERR")
    if [[ "$anon_count" == "0" ]]; then
      pass_check "RLS blocks anon on pmoves_core.$tbl (count=0)"
    elif [[ "$anon_count" == "ERR" ]]; then
      pass_check "RLS blocks anon on pmoves_core.$tbl (query denied/error)"
    else
      fail_check "Anon can read pmoves_core.$tbl (count=$anon_count) — RLS not enforced"
    fi

    # Service role: should be able to query
    if [[ -n "${SUPABASE_DB_URL_SERVICE:-}" ]]; then
      local svc_result
      svc_result=$(psql "$SUPABASE_DB_URL_SERVICE" -t -A -c "SELECT count(*) FROM pmoves_core.$tbl;" 2>/dev/null || echo "ERR")
      if [[ "$svc_result" != "ERR" ]]; then
        pass_check "service_role can query pmoves_core.$tbl (count=$svc_result)"
      else
        fail_check "service_role cannot query pmoves_core.$tbl — check credentials"
      fi
    else
      warn_check "SUPABASE_DB_URL_SERVICE not set — cannot verify service_role access for $tbl"
    fi
  done
}

# ============================================================================
# 2. pg_stats Lockdown Verification (CVE-2025-8713, PR #1331)
# ============================================================================
check_pg_stats_lockdown() {
  section "2. pg_stats / pg_statistic lockdown — CVE-2025-8713 (PR #1331)"

  if [[ -z "${SUPABASE_DB_URL_ANON:-}" ]]; then
    warn_check "SUPABASE_DB_URL_ANON not set — skipping pg_stats checks"
    return 0
  fi

  if ! psql "$SUPABASE_DB_URL_ANON" -c "SELECT 1" &>/dev/null; then
    warn_check "Supabase DB not reachable — skipping pg_stats checks"
    return 0
  fi

  # pg_stats
  local pg_stats_out
  pg_stats_out=$(psql "$SUPABASE_DB_URL_ANON" -c "SELECT * FROM pg_stats LIMIT 1;" 2>&1) || true
  if echo "$pg_stats_out" | grep -qi 'permission denied'; then
    pass_check "pg_stats: anon gets permission denied"
  elif echo "$pg_stats_out" | grep -qi 'does not exist\|relation'; then
    pass_check "pg_stats: anon cannot access (relation blocked)"
  else
    fail_check "pg_stats: anon can read — CVE-2025-8713 NOT mitigated"
  fi

  # pg_statistic
  local pg_stat_out
  pg_stat_out=$(psql "$SUPABASE_DB_URL_ANON" -c "SELECT * FROM pg_statistic LIMIT 1;" 2>&1) || true
  if echo "$pg_stat_out" | grep -qi 'permission denied'; then
    pass_check "pg_statistic: anon gets permission denied"
  elif echo "$pg_stat_out" | grep -qi 'does not exist\|relation'; then
    pass_check "pg_statistic: anon cannot access (relation blocked)"
  else
    fail_check "pg_statistic: anon can read — CVE-2025-8713 NOT mitigated"
  fi
}

# ============================================================================
# 3. Qdrant API Key Verification (PR #1333)
# ============================================================================
check_qdrant_auth() {
  section "3. Qdrant API key enforcement (PR #1333)"

  if ! port_up 6333; then
    warn_check "Qdrant port 6333 not reachable — skipping"
    return 0
  fi

  local unauth
  unauth=$(curl -s --max-time 5 http://localhost:6333/collections)
  if echo "$unauth" | grep -qi 'unauthorized\|forbidden\|401\|403'; then
    pass_check "Qdrant rejects unauthenticated request"
  else
    fail_check "Qdrant allows unauthenticated request — API key not enforced"
  fi

  if [[ -n "${QDRANT_API_KEY:-}" ]]; then
    local authed
    authed=$(curl -s --max-time 5 -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections)
    if echo "$authed" | grep -q 'result'; then
      pass_check "Qdrant accepts authenticated request with API key"
    else
      fail_check "Qdrant rejects authenticated request — check QDRANT_API_KEY"
    fi
  else
    warn_check "QDRANT_API_KEY not set — cannot verify authenticated access"
  fi
}

# ============================================================================
# 4. Neo4j Auth Verification (PR #1333)
# ============================================================================
check_neo4j_auth() {
  section "4. Neo4j authentication enforcement (PR #1333)"

  if ! port_up 7474; then
    warn_check "Neo4j port 7474 not reachable — skipping"
    return 0
  fi

  local unauth
  unauth=$(curl -s --max-time 5 http://localhost:7474/db/neo4j/tx/commit)
  if echo "$unauth" | grep -qi 'unauthorized\|error\|forbidden'; then
    pass_check "Neo4j rejects unauthenticated request"
  else
    fail_check "Neo4j allows unauthenticated request — auth not enforced"
  fi

  if [[ -n "${NEO4J_PASSWORD:-}" ]]; then
    local authed
    authed=$(curl -s --max-time 5 -u "neo4j:$NEO4J_PASSWORD" \
      http://localhost:7474/db/neo4j/tx/commit \
      -H "Content-Type: application/json" \
      -d '{"statements":[{"statement":"RETURN 1"}]}')
    if echo "$authed" | grep -q 'results'; then
      pass_check "Neo4j accepts authenticated request"
    else
      fail_check "Neo4j rejects authenticated request — check NEO4J_PASSWORD"
    fi
  else
    warn_check "NEO4J_PASSWORD not set — cannot verify authenticated access"
  fi
}

# ============================================================================
# 5. Meilisearch Master Key Verification (PR #1333)
# ============================================================================
check_meilisearch_auth() {
  section "5. Meilisearch master key enforcement (PR #1333)"

  if ! port_up 7700; then
    warn_check "Meilisearch port 7700 not reachable — skipping"
    return 0
  fi

  local unauth
  unauth=$(curl -s --max-time 5 http://localhost:7700/indexes)
  if echo "$unauth" | grep -qi 'missing\|invalid\|unauthorized\|forbidden'; then
    pass_check "Meilisearch rejects unauthenticated request"
  else
    fail_check "Meilisearch allows unauthenticated request — master key not enforced"
  fi

  if [[ -n "${MEILI_MASTER_KEY:-}" ]]; then
    local authed
    authed=$(curl -s --max-time 5 -H "Authorization: Bearer $MEILI_MASTER_KEY" http://localhost:7700/indexes)
    if echo "$authed" | grep -q 'results\|^\[\]'; then
      pass_check "Meilisearch accepts authenticated request with master key"
    else
      fail_check "Meilisearch rejects authenticated request — check MEILI_MASTER_KEY"
    fi
  else
    warn_check "MEILI_MASTER_KEY not set — cannot verify authenticated access"
  fi
}

# ============================================================================
# 6. Anon→Service_Role Migration Audit (PR #1331 breaking change)
# ============================================================================
check_anon_migration() {
  section "6. Anon→service_role migration audit — no writes via ANON_KEY (PR #1331)"
  local violations=()

  if [[ ! -d "$REPO_ROOT/pmoves" ]]; then
    warn_check "pmoves/ directory not found — skipping"
    return 0
  fi

  while IFS= read -r -d '' f; do
    if grep -qiE '\b(insert|update|delete|create)\b' "$f" 2>/dev/null; then
      local code_lines
      code_lines=$(grep -n -iE '\b(insert|update|delete|create)\b' "$f" 2>/dev/null \
        | grep -v '^[[:space:]]*#\|^[[:space:]]*//\|^[[:space:]]*\*\|^[[:space:]]*"""' \
        | grep -v ' noqa\|type:ignore' || true)
      if [[ -n "$code_lines" ]]; then
        violations+=("$f")
        echo -e "  ${RED}FAIL${NC} $f uses ANON_KEY and contains write operations"
        echo "$code_lines" | head -5 | sed 's/^/         /'
      fi
    fi
  done < <(grep -rl 'SUPABASE_ANON_KEY\|ANON_KEY' "$REPO_ROOT/pmoves" \
    --include='*.py' --include='*.ts' --include='*.js' --include='*.env*' 2>/dev/null \
    | grep -v '__pycache__' | grep -v 'node_modules' | grep -v '\.example' || true)

  if [[ ${#violations[@]} -eq 0 ]]; then
    pass_check "No source files use ANON_KEY with write operations"
  else
    for _ in "${violations[@]}"; do
      FAIL=$((FAIL + 1))
      TOTAL=$((TOTAL + 1))
    done
  fi
}

# ============================================================================
# 7. Headscale ACL Verification (PR #1327)
# ============================================================================
check_headscale_acl() {
  section "7. Headscale ACL syntax + exit node rules (PR #1327)"

  if [[ ! -f "$ACL_YAML" ]]; then
    warn_check "acl.yaml not found at $ACL_YAML — skipping"
    return 0
  fi

  # YAML syntax validation
  if python3 -c "import yaml; yaml.safe_load(open('$ACL_YAML'))" 2>/dev/null; then
    pass_check "acl.yaml is valid YAML"
  else
    fail_check "acl.yaml has invalid YAML syntax"
    return 0
  fi

  # Check exit node autogroup:internet rules have proper client groups as src
  local exit_rules
  exit_rules=$(grep -A10 'autogroup:internet' "$ACL_YAML" 2>/dev/null || true)
  if [[ -z "$exit_rules" ]]; then
    warn_check "No autogroup:internet rules found in acl.yaml"
    return 0
  fi

  if echo "$exit_rules" | grep -q 'group:admin\|group:users'; then
    pass_check "Exit node rules use client groups (group:admin/group:users) as src"
  else
    fail_check "Exit node rules missing client group src — may use tag:exit instead of group:*"
  fi

  # Check no overly permissive wildcard-to-autogroup:internet rules
  if echo "$exit_rules" | grep -q '\*:\*'; then
    fail_check "Wildcard (*:*) rule targets autogroup:internet — overly permissive"
  else
    pass_check "No wildcard rules targeting autogroup:internet"
  fi

  # -- Headscale latest-version config format checks --
  if [[ -f "$CONFIG_YAML" ]]; then
    # Validate prefixes (not deprecated ip_prefixes)
    if grep -q '^prefixes:' "$CONFIG_YAML" 2>/dev/null; then
      pass_check "config.yaml uses 'prefixes:' (latest format)"
    else
      fail_check "config.yaml missing 'prefixes:' — may still use deprecated 'ip_prefixes:'"
    fi

    # Validate noise.private_key_path for Tailscale v2
    if grep -q 'noise:' "$CONFIG_YAML" 2>/dev/null \
       && grep -q 'private_key_path:' "$CONFIG_YAML" 2>/dev/null; then
      pass_check "config.yaml contains noise.private_key_path (Tailscale v2)"
    else
      fail_check "config.yaml missing noise.private_key_path — required for latest Headscale"
    fi

    # Validate dns.nameservers.global (not flat dns_config.nameservers)
    if grep -qE '^dns:|nameservers:\s*$' "$CONFIG_YAML" 2>/dev/null \
       && grep -qE 'global:' "$CONFIG_YAML" 2>/dev/null; then
      pass_check "config.yaml uses dns.nameservers.global (latest format)"
    else
      fail_check "config.yaml missing dns.nameservers.global — may still use flat dns_config"
    fi
  else
    warn_check "config.yaml not found at $CONFIG_YAML — skipping format checks"
  fi
}

# ============================================================================
# 8. Docker Image Version Verification (PR #1332)
# ============================================================================
check_docker_versions() {
  section "8. Docker image CVE-upgraded versions (PR #1332)"

  local checks=(
    "$COMPOSE_CORE:qdrant/qdrant:v1.16.0:Qdrant v1.16.0"
    "$COMPOSE_CORE:getmeili/meilisearch:v1.34.1:Meilisearch v1.34.1"
    "$COMPOSE_CORE:neo4j:5.26.22:Neo4j 5.26.22"
    "$COMPOSE_CORE:supabase/postgres:17.6.1.108:Supabase Postgres 17.6.1.108"
    "$COMPOSE_N8N:pmoves/n8n:2.1.5-runtime:n8n 2.1.5 (runtime)"
  )

  for entry in "${checks[@]}"; do
    IFS=':' read -r file tag desc <<< "$entry"
    if [[ ! -f "$file" ]]; then
      warn_check "$desc — compose file not found ($file)"
      continue
    fi
    if grep -q "$tag" "$file"; then
      pass_check "$desc present in $(basename "$file")"
    else
      fail_check "$desc NOT found in $(basename "$file") — CVE fix may be missing"
    fi
  done
}

# ============================================================================
# 9. No Hardcoded Credentials (PMOVES hard rule)
# ============================================================================
check_no_hardcoded_creds() {
  section "9. No hardcoded credentials in env files (PMOVES hard rule)"

  local files=("$ENV_DATA_EXAMPLE" "$ENV_SUPA_EXAMPLE")
  local patterns=("changeme" "minioadmin")
  local fail_count=0

  for f in "${files[@]}"; do
    if [[ ! -f "$f" ]]; then
      warn_check "$(basename "$f") not found — skipping"
      continue
    fi
    for pat in "${patterns[@]}"; do
      while IFS= read -r match; do
        [[ -z "$match" ]] && continue
        local lineno content
        lineno=$(echo "$match" | cut -d: -f1)
        content=$(echo "$match" | cut -d: -f2-)
        # Allow if line explicitly says to replace/change it
        if ! echo "$content" | grep -qi 'replace\|do not use\|example\|placeholder\|change this'; then
          echo -e "  ${RED}FAIL${NC} $(basename "$f"):$lineno contains hardcoded '$pat'"
          fail_count=$((fail_count + 1))
        fi
      done < <(grep -n "$pat" "$f" 2>/dev/null || true)
    done
  done

  # Check live env files (non-example) — these are NEVER acceptable
  while IFS= read -r -d '' f; do
    for pat in "${patterns[@]}"; do
      while IFS= read -r match; do
        [[ -z "$match" ]] && continue
        local lineno=$(echo "$match" | cut -d: -f1)
        echo -e "  ${RED}FAIL${NC} $(basename "$f"):$lineno contains hardcoded '$pat' in live env file"
        fail_count=$((fail_count + 1))
      done < <(grep -n "$pat" "$f" 2>/dev/null || true)
    done
  done < <(find "$REPO_ROOT/pmoves" -maxdepth 1 -name 'env.*' ! -name '*.example' -print0 2>/dev/null)

  if [[ $fail_count -eq 0 ]]; then
    pass_check "No hardcoded credentials found in env files"
  else
    for _ in $(seq 1 $fail_count); do
      FAIL=$((FAIL + 1))
      TOTAL=$((TOTAL + 1))
    done
  fi
}

# ============================================================================
# Main
# ============================================================================
main() {
  echo -e "${CYAN}============================================================${NC}"
  echo -e "${CYAN} PMOVES Post-Merge Security Verification${NC}"
  echo -e "${CYAN} PRs: #1327 #1331 #1332 #1333${NC}"
  echo -e "${CYAN} $(date -u '+%Y-%m-%dT%H:%M:%SZ')${NC}"
  echo -e "${CYAN}============================================================${NC}"

  check_supabase_rls
  check_pg_stats_lockdown
  check_qdrant_auth
  check_neo4j_auth
  check_meilisearch_auth
  check_anon_migration
  check_headscale_acl
  check_docker_versions
  check_no_hardcoded_creds

  # -- Summary ---------------------------------------------------------------
  echo -e "\n${CYAN}============================================================${NC}"
  echo -e " ${GREEN}PASS: $PASS${NC}  ${RED}FAIL: $FAIL${NC}  ${YELLOW}WARN: $WARN${NC}  (of $TOTAL checks)"
  echo -e "${CYAN}============================================================${NC}"

  if [[ $FAIL -gt 0 ]]; then
    echo -e " ${RED}VERIFICATION FAILED — $FAIL check(s) need attention${NC}"
    exit 1
  elif [[ $WARN -gt 0 ]]; then
    echo -e " ${YELLOW}VERIFICATION PASSED with $WARN warning(s)${NC}"
    exit 0
  else
    echo -e " ${GREEN}ALL CHECKS PASSED${NC}"
    exit 0
  fi
}

main "$@"
