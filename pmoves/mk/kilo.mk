# pmoves/mk/kilo.mk
#
# KiloCode GLM operational targets: health probe and parity check.
# The launcher itself is `make -C pmoves kilo` (pmoves/scripts/kilo-pmoves.sh).
# See pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md.

REPO_ROOT := $(abspath $(CURDIR)/..)
KILO_JSON := $(REPO_ROOT)/kilo.json
KILORULES := $(REPO_ROOT)/.kilocode/rules/kilorules.md
KILOMODES := $(REPO_ROOT)/.kilocodemodes
KILO_AGENT_DIR := $(REPO_ROOT)/.kilo/agent

KILO_HEALTH_TIMEOUT ?= 5

.PHONY: kilo-help kilo-health kilo-parity-check

# ---------- Help ----------

kilo-help: ## Show KiloCode GLM operational targets
	@echo "KiloCode GLM targets:"
	@echo "  kilo              Launch KiloCode/OpenCode CLI (existing target; see scripts/kilo-pmoves.sh)"
	@echo "  kilo-health       Probe TensorZero/Ollama/Cipher health + optional NATS heartbeat"
	@echo "  kilo-parity-check Report parity gaps vs Kimi/Codex/Claude lanes"
	@echo "  kilo-help         This message"

# ---------- Health ----------

kilo-health: ## Probe KiloCode GLM dependency health (TensorZero, Ollama, Cipher)
	@echo "[*] KiloCode GLM health check ..."
	@set -a; $(LOAD_ENV_SHARED) 2>/dev/null || true; set +a; \
	ok=0; fail=0; \
	_probe() { \
	  name="$$1"; url="$$2"; \
	  if curl -fsS --max-time $(KILO_HEALTH_TIMEOUT) "$$url" >/dev/null 2>&1; then \
	    echo "  ✅ $$name  ($$url)"; ok=$$((ok+1)); \
	  else \
	    echo "  ❌ $$name  ($$url)"; fail=$$((fail+1)); \
	  fi; \
	}; \
	_probe "TensorZero" "http://localhost:3030/health"; \
	_probe "Ollama" "http://localhost:11434/api/tags"; \
	_probe "Cipher" "http://localhost:8105/health"; \
	echo "[*] Results: $$ok healthy, $$fail unhealthy"; \
	if [ -n "$${NATS_URL:-}" ] && command -v nats >/dev/null 2>&1; then \
	  nats pub kilocode.agent.status.v1 \
	    "{\"agent\":\"kilocode_glm\",\"healthy\":$$ok,\"unhealthy\":$$fail,\"ts\":\"$$(date -Iseconds)\"}" \
	    2>/dev/null && echo "[+] Heartbeat published to kilocode.agent.status.v1" \
	    || echo "[!] Could not publish heartbeat (NATS unreachable?)"; \
	fi; \
	exit $$fail

# ---------- Parity ----------

kilo-parity-check: ## Report parity gaps between KiloCode GLM and Kimi/Codex/Claude lanes
	@echo "[*] KiloCode GLM parity check ..."
	@gaps=0; blocked=0; \
	_check() { \
	  name="$$1"; path="$$2"; \
	  if [ -e "$$path" ]; then \
	    echo "  ✅ $$name"; \
	  else \
	    echo "  ❌ $$name  (expected $$path)"; gaps=$$((gaps+1)); \
	  fi; \
	}; \
	_check_blocked() { \
	  name="$$1"; path="$$2"; reason="$$3"; \
	  if [ -e "$$path" ]; then \
	    echo "  ✅ $$name"; \
	  else \
	    echo "  ⚠️  $$name  (blocked by platform — $$reason)"; blocked=$$((blocked+1)); \
	  fi; \
	}; \
	_check "KiloCode config" "$(KILO_JSON)"; \
	_check "KiloCode rules" "$(KILORULES)"; \
	_check "KiloCode modes" "$(KILOMODES)"; \
	_check "KiloCode agent profile" "$(REPO_ROOT)/pmoves/configs/agent-profiles/kilocode_glm.yaml"; \
	_check "KiloCode operator home" "$(REPO_ROOT)/pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md"; \
	_check "KiloCode parity map" "$(REPO_ROOT)/pmoves/docs/AGENTS/KILOCODE_CLAUDE_PARITY_MAP.md"; \
	_check "KiloCode persona playbook" "$(REPO_ROOT)/pmoves/docs/AGENTS/KILOCODE_PERSONA_STYLE_PLAYBOOK.md"; \
	_check "KiloCode bringup-audit skill" "$(REPO_ROOT)/.kilocode/skills/kilocode-bringup-audit/SKILL.md"; \
	_check "KiloCode agent-trails skill" "$(REPO_ROOT)/.kilocode/skills/kilocode-agent-trails/SKILL.md"; \
	echo ""; \
	echo "  Damage-Control Hooks (Issue #2120):"; \
	_check "  Damage-control patterns" "$(REPO_ROOT)/.kilo/hooks/damage-control/patterns.yaml"; \
	_check "  Damage-control README" "$(REPO_ROOT)/.kilo/hooks/damage-control/README.md"; \
	_check_blocked "  Hook implementation" "$(REPO_ROOT)/.kilo/hooks/pre-tool.sh" "awaiting KiloCode/OpenCode hook API"; \
	echo ""; \
	_check "Agent registry entry" "$(REPO_ROOT)/pmoves/config/agent_registry.yaml"; \
	if grep -q '^  kilocode_glm:' "$(REPO_ROOT)/pmoves/config/agent_registry.yaml" 2>/dev/null; then \
	  echo "  ✅ kilocode_glm registry entry"; \
	else \
	  echo "  ❌ kilocode_glm registry entry"; gaps=$$((gaps+1)); \
	fi; \
	if grep -q 'make -C pmoves kilo' "$(REPO_ROOT)/.kimi/AGENTS.md" 2>/dev/null; then \
	  echo "  ✅ KiloCode cross-linked in .kimi/AGENTS.md"; \
	else \
	  echo "  ❌ KiloCode cross-linked in .kimi/AGENTS.md"; gaps=$$((gaps+1)); \
	fi; \
	echo ""; \
	mcp_gaps=$$(PYTHONPATH="$(CURDIR)/.." $(PYTHON) -m pmoves.tools.kilo_parity_mcp_check); \
	gaps=$$((gaps + mcp_gaps)); \
	if [ $$blocked -gt 0 ]; then \
	  echo "[*] Results: $$gaps gap(s) found, $$blocked item(s) blocked by platform (expected)"; \
	else \
	  echo "[*] Results: $$gaps gap(s) found"; \
	fi; \
	exit $$gaps
	exit $$gaps
