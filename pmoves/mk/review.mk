# review.mk — Review collection and dump targets

.PHONY: review-dump review-dump-all review-dump-ingest review-collect-help

REVIEW_REPO ?= PMOVES.AI
REVIEW_PR ?=
REVIEW_STATE ?= open
REVIEW_LIMIT ?= 20

## Review dump: collect PR threads into LLM-readable JSON + Markdown
review-dump:
ifdef REVIEW_PR
	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --pr $(REVIEW_PR) --dry-run
else
	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --state $(REVIEW_STATE) --limit $(REVIEW_LIMIT) --dry-run
endif

## Review dump with Hi-RAG + Cipher ingestion (requires services up)
review-dump-ingest:
ifdef REVIEW_PR
	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --pr $(REVIEW_PR) --ingest-hirag --ingest-cipher
else
	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --state $(REVIEW_STATE) --limit $(REVIEW_LIMIT) --ingest-hirag --ingest-cipher
endif

## Dump all open PRs across the org
review-dump-all:
	@FAILED=0; \
	for repo in PMOVES.AI PMOVES-Agent-Zero PMOVES-Archon PMOVES-BoTZ PMOVES-Creator PMOVES-HiRAG PMOVES-ToKenism-Multi PMOVES-DoX; do \
		echo "--- $$repo ---"; \
		bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $$repo --state open --limit 5 --dry-run || { echo "FAILED: $$repo"; FAILED=1; }; \
	done; \
	[ "$$FAILED" -eq 0 ]

review-collect-help:
	@echo "Review collection targets:"
	@echo "  make review-dump REVIEW_PR=2434          # dump a single PR"
	@echo "  make review-dump REVIEW_REPO=Pmoves-cipher  # dump from a submodule"
	@echo "  make review-dump-all                     # dump all open PRs across org"
	@echo "  make review-dump-ingest REVIEW_PR=2434   # dump + ingest into Hi-RAG + Cipher"
	@echo ""
	@echo "Output: pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md}"
