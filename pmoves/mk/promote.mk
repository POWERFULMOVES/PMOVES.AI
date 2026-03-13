# PMOVES.AI Branch Promotion Helper
# Provides canonical commands for branch promotion following the documented strategy
# See: pmoves/docs/BRANCH_STRATEGY.md

.PHONY: promote-to-integrations promote-to-hardened promote-to-main promote-check publish-nats-promotion

# NATS configuration (load from environment or use defaults)
NATS_URL ?= nats://nats:pmoves@nats:4222
NATS_SUBJECT_PREFIX ?= github.promotion

# Publish promotion event to NATS
publish-nats-promotion:
	@echo "Publishing promotion event to NATS..."
	@nats pub "$(NATS_URL)" "$(NATS_SUBJECT_PREFIX).requested.v1" \
		'{$(promote_payload)}' || echo "ℹ️  NATS publish failed (continuing)"
	@echo "✅ Promotion event published"

# Default target
promote-help:
	@echo "PMOVES.AI Branch Promotion Helper"
	@echo ""
	@echo "Usage:"
	@echo "  make -C pmoves promote-to-integrations   # From feature branch"
	@echo "  make -C pmoves promote-to-hardened       # From Integrations branch"
	@echo "  make -C pmoves promote-to-main           # From Hardened branch"
	@echo "  make -C pmoves promote-check             # Validate current branch state"
	@echo ""
	@echo "Branch Promotion Flow:"
	@echo "  feature/* → PMOVES.AI-Edition-Hardened-Integrations → PMOVES.AI-Edition-Hardened → main"
	@echo ""

# Check if branch is clean and ready for promotion
promote-check:
	@echo "Checking branch state..."
	@git diff --quiet || (echo "❌ Working directory has uncommitted changes" && exit 1)
	@git diff --cached --quiet || (echo "❌ Staged changes detected" && exit 1)
	@echo "✅ Working directory clean"
	@echo ""
	@echo "Current branch: $$(git branch --show-current)"
	@echo "Tracking branch: $$(git rev-parse --abbrev-ref --symbolic-full-name @{u})"
	@echo "Commit count: $$(git rev-list --count HEAD ^@{u}) ahead of $$(git rev-parse --abbrev-ref --symbolic-full-name @{u})"
	@echo ""

# Feature → Integrations
promote-to-integrations: promote-check
	@echo "Creating PR: feature → Integrations"
	@echo ""
	@read -p "PR title (or press Enter for auto-generated): " title; \
	if [ -z "$$title" ]; then \
		title="promote: $$(git branch --show-current) → Integrations"; \
	fi; \
	pr_number=$$(gh pr create \
		--base PMOVES.AI-Edition-Hardened-Integrations \
		--title "$$title" \
		--body "## Promotion Summary

This PR promotes changes from **$$(git branch --show-current)** to the **Integrations** branch.

### Changes
$$(git log --oneline @{u}...HEAD | sed 's/^/- /')

### CI Gates
- [ ] integration-gate workflow must pass

### Promotion Flow
1. Feature branch (here) → Integrations (CI gate)
2. Integrations → Hardened (audit gate)
3. Hardened → main (release)

---
*Automated via make -C pmoves promote-to-integrations*" \
		--json number --jq '.number'); \
	$(MAKE) publish-nats-promotion \
		promote_payload='"action":"feature_to_integrations","branch":"$$(git branch --show-current)","pr_number":"'$$pr_number'","target":"PMOVES.AI-Edition-Hardened-Integrations","timestamp":"$$(date -u +%Y-%m-%dT%H:%M:%SZ)"'
	@echo ""
	@echo "✅ PR created successfully!"
	@echo "🔗 Monitor: integration-gate workflow"
	@echo ""

# Integrations → Hardened
promote-to-hardened: promote-check
	@echo "Creating promotion PR: Integrations → Hardened"
	@echo ""
	@echo "⚠️  This will trigger the full audit gate (security + contract validation)"
	@read -p "Continue? (y/N): " confirm; \
	if [ "$$confirm" != "y" ]; then \
		echo "❌ Aborted"; \
		exit 1; \
	fi
	@read -p "PR title (or press Enter for auto-generated): " title; \
	if [ -z "$$title" ]; then \
		title="promote: Integrations → Hardened [$$(date +%Y-%m-%d)]"; \
	fi; \
	pr_number=$$(gh pr create \
		--base PMOVES.AI-Edition-Hardened \
		--head PMOVES.AI-Edition-Hardened-Integrations \
		--title "$$title" \
		--body "## Promotion Summary

This PR promotes the **Integrations** branch to **Hardened**.

### Audit Gates
- [ ] integration-gate workflow
- [ ] hardening-validation workflow
- [ ] CodeQL analysis
- [ ] CHIT contract validation
- [ ] SQL policy lint

### Review Required
This promotion requires security review before merging.

### Changes Included
$$(git log --oneline PMOVES.AI-Edition-Hardened...PMOVES.AI-Edition-Hardened-Integrations | head -20 | sed 's/^/- /')

---
*Automated via make -C pmoves promote-to-hardened*" \
		--json number --jq '.number'); \
	$(MAKE) publish-nats-promotion \
		promote_payload='"action":"integrations_to_hardened","branch":"PMOVES.AI-Edition-Hardened-Integrations","pr_number":"'$$pr_number'","target":"PMOVES.AI-Edition-Hardened","timestamp":"$$(date -u +%Y-%m-%dT%H:%M:%SZ)"'
	@echo ""
	@echo "✅ Promotion PR created!"
	@echo "⚠️  Requires security review approval"
	@echo "🔗 Monitor: integration-gate + hardening-validation workflows"
	@echo ""

# Hardened → Main (Release)
promote-to-main: promote-check
	@echo "Creating release PR: Hardened → main"
	@echo ""
	@echo "⚠️  This is a PRODUCTION RELEASE"
	@read -p "Release version (e.g., v1.2.3): " version; \
	if [ -z "$$version" ]; then \
		echo "❌ Version required"; \
		exit 1; \
	fi; \
	read -p "Release notes filename (optional): " notes_file; \
	echo ""; \
	echo "Release: $$version"; \
	echo "Base: main"; \
	echo "Head: PMOVES.AI-Edition-Hardened"; \
	echo ""; \
	read -p "Confirm release creation? (y/N): " confirm; \
	if [ "$$confirm" != "y" ]; then \
		echo "❌ Aborted"; \
		exit 1; \
	fi; \
	body="## Release $$version

This release promotes **Hardened** changes to **main** production.

### All CI Gates Must Pass
- [ ] CodeQL (Advanced)
- [ ] CHIT Contract Check
- [ ] SQL Policy Lint
- [ ] integration-gate
- [ ] hardening-validation

### Post-Merge Actions
\`\`\`bash
# Tag the release
git tag -a $$version -m \"Release $$version\"
git push origin $$version
\`\`\`

---
*Automated via make -C pmoves promote-to-main*"; \
	if [ -n "$$notes_file" ] && [ -f "$$notes_file" ]; then \
		body="$$(cat $$notes_file)"; \
	fi; \
	pr_number=$$(gh pr create \
		--base main \
		--head PMOVES.AI-Edition-Hardened \
		--title "release: $$version hardened → main" \
		--body "$$body" \
		--json number --jq '.number'); \
	$(MAKE) publish-nats-promotion \
		promote_payload='"action":"hardened_to_main","branch":"PMOVES.AI-Edition-Hardened","pr_number":"'$$pr_number'","target":"main","release_version":"$$version","timestamp":"$$(date -u +%Y-%m-%dT%H:%M:%SZ)"'
	@echo ""
	@echo "✅ Release PR created!"
	@echo "⚠️  All CI gates must pass before merge"
	@echo "📋 After merge: git tag $$version && git push origin $$version"
	@echo ""
