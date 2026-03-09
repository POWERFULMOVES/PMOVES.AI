# pmoves/mk/build-gate.mk — Local build validation gates
# ======================================================
# Pre-dispatch validation: verify Docker builds locally before
# sending work to CI runners.  Runners are execution muscle,
# not test beds.
#
# Usage:
#   make -C pmoves build-gate SERVICE=agent-zero
#   make -C pmoves build-gate-ci
#   make -C pmoves build-gate-dry

.PHONY: build-gate build-gate-all build-gate-ci build-gate-lint build-gate-dry \
       build-gate-check build-gate-audit build-gate-audit-all \
       build-gate-validate-ci build-gate-full

build-gate: ## Validate a single service Docker build locally (SERVICE=name)
	$(if $(strip $(SERVICE)),,$(error Usage: make -C pmoves build-gate SERVICE=<name>))
	@$(CODEX_PY) tools/build_gate.py --service "$(SERVICE)" $(ARGS)

build-gate-all: ## Validate ALL images in images.yaml build locally
	@$(CODEX_PY) tools/build_gate.py --all $(ARGS)

build-gate-ci: ## Validate only CI matrix images (integrations-ghcr.matrix.json)
	@$(CODEX_PY) tools/build_gate.py --ci-matrix $(ARGS)

build-gate-lint: ## Lint Dockerfiles with hadolint (if available)
	@$(CODEX_PY) tools/build_gate.py --ci-matrix --lint $(ARGS)

build-gate-dry: ## Dry-run: show resolved build contexts without building
	@$(CODEX_PY) tools/build_gate.py --ci-matrix --dry-run $(ARGS)

build-gate-check: ## Run BuildKit --check on CI matrix Dockerfiles (fast, no build)
	@$(CODEX_PY) tools/build_gate.py --ci-matrix --check $(ARGS)

build-gate-audit: ## Audit CI matrix Dockerfiles for hardening compliance
	@$(CODEX_PY) tools/build_gate.py --ci-matrix --audit $(ARGS)

build-gate-audit-all: ## Audit ALL images.yaml Dockerfiles for hardening compliance
	@$(CODEX_PY) tools/build_gate.py --all --audit $(ARGS)

build-gate-validate-ci: ## Validate CI matrix field references (trivy, build_args)
	@$(CODEX_PY) tools/build_gate.py --ci-matrix --validate-ci $(ARGS)

build-gate-full: ## Full pre-dispatch gate: audit + check + lint (no build)
	@$(CODEX_PY) tools/build_gate.py --ci-matrix --audit --check --lint $(ARGS)
