# pr-review.mk — PR review trim cycle + listening targets
#
# The review-trim cycle (Mavis-5090's "learnings-first, conformance-gated"
# style) has two halves:
#   - LISTEN: detect when a review arrives (pr-review-watch)
#   - ACT:    run the trim cycle on the comments (pr-review-trim)
#
# The listen half wraps pmoves/tools/pr_review_watcher.py. Three modes:
#   - notifications (default) — HTTP ETag on /notifications, no public URL
#   - pr-watch     — per-PR review state diff
#   - nats         — subscribe to github.webhook.review.* (B mode, n8n up)
#
# Usage:
#   make -C pmoves pr-review-watch PRS="2132,2133,2134" MAX_RUNTIME=24h
#   make -C pmoves pr-review-watch-mode MODE=pr-watch PR=2132
#   make -C pmoves pr-review-watch-mode MODE=nats
#   make -C pmoves pr-review-watch-daemon PRS="2132,2133,2134"  # nohup background
#   make -C pmoves pr-review-trim PR=2132                        # run the trim
#   make -C pmoves pr-review-tail                                # tail the log
#   make -C pmoves pr-review-status                              # quick health check
#
# Requirements:
#   - gh CLI authed (gh auth status)
#   - for nats mode: nats-py installed (uv pip install nats-py) OR nats CLI

# Paths are relative to the repo ROOT. Resolve via git so it works in
# both main and worktree checkouts.
PMOVES_ROOT := $(shell git rev-parse --show-toplevel)
PR_WATCHER := $(PMOVES_ROOT)/pmoves/tools/pr_review_watcher.py
PR_TRIMMER := $(PMOVES_ROOT)/pmoves/tools/pr_hedge_trim.py
PR_ARRIVAL_LOG := $(PMOVES_ROOT)/pmoves/docs/logs/pr_review_arrivals.jsonl
PR_WATCHER_OUT := $(PMOVES_ROOT)/pmoves/docs/logs/pr_review_watcher.out

PRS ?= 2132,2133,2134
MODE ?= notifications
PR ?= 2132
MAX_RUNTIME ?= 1h
INTERVAL ?= 30
MAX_INTERVAL ?= 300

.PHONY: pr-review-watch pr-review-watch-mode pr-review-watch-daemon pr-review-tail pr-review-status pr-review-help

pr-review-help:
	@echo "pr-review targets:"
	@echo "  pr-review-watch PRS=<N,M,...>  listen in foreground (default mode=notifications)"
	@echo "  pr-review-watch-mode MODE=<m> PR=<N>  one-shot, mode in {notifications,pr-watch,nats}"
	@echo "  pr-review-watch-daemon PRS=<N,M,...>  nohup background, 7-day max-runtime"
	@echo "  pr-review-tail  tail the arrivals log"
	@echo "  pr-review-status  quick health check (last 5 arrivals, watcher PID)"
	@echo "  pr-review-trim PR=<N>  run the trim cycle on PR #N"
	@echo ""
	@echo "Current: PRS=$(PRS), MODE=$(MODE), PR=$(PR), MAX_RUNTIME=$(MAX_RUNTIME)"

# Foreground watch (default mode = notifications)
pr-review-watch:
	python $(PR_WATCHER) --mode $(MODE) --prs $(PRS) --max-runtime $(MAX_RUNTIME) --interval $(INTERVAL) --max-interval $(MAX_INTERVAL) --log $(PR_ARRIVAL_LOG) --emit-nats

# Single-PR watch (pr-watch mode) or one-shot NATS subscribe
pr-review-watch-mode:
	python $(PR_WATCHER) --mode $(MODE) --pr $(PR) --max-runtime $(MAX_RUNTIME) --interval $(INTERVAL) --max-interval $(MAX_INTERVAL) --log $(PR_ARRIVAL_LOG) --emit-nats

# Daemon mode: 7-day max-runtime, logs to JSONL + stdout, emits NATS, nohup
pr-review-watch-daemon:
	@mkdir -p $$(dirname $(PR_ARRIVAL_LOG))
	@nohup python $(PR_WATCHER) --mode $(MODE) --prs $(PRS) --max-runtime 168h --interval $(INTERVAL) --max-interval $(MAX_INTERVAL) --log $(PR_ARRIVAL_LOG) --emit-nats > $(PR_WATCHER_OUT) 2>&1 &
	@echo "watcher daemon started (PID $$!), logging to $(PR_ARRIVAL_LOG)"
	@echo "  tail: make -C pmoves pr-review-tail"
	@echo "  stop: kill $$(jobs -p)  # or use Task Manager / pkill -f pr_review_watcher"

# Tail the arrivals log (this IS subscribing — bash tail -f is event-driven)
pr-review-tail:
	@if [ -f $(PR_ARRIVAL_LOG) ]; then tail -f $(PR_ARRIVAL_LOG); else echo "no arrivals yet — start the daemon with make -C pmoves pr-review-watch-daemon"; fi

# Quick health check
pr-review-status:
	@echo "== arrivals log =="
	@if [ -f $(PR_ARRIVAL_LOG) ]; then wc -l $(PR_ARRIVAL_LOG); tail -5 $(PR_ARRIVAL_LOG) | python -m json.tool --no-ensure-ascii 2>/dev/null || tail -5 $(PR_ARRIVAL_LOG); else echo "(no log yet)"; fi
	@echo ""
	@echo "== watcher process =="
	@pgrep -f pr_review_watcher.py 2>/dev/null | head -5 || echo "(not running)"
	@echo ""
	@echo "== outbound NATS subject =="
	@echo "  chit.pr.review.detected.v1 (set with NATS_URL)"

# Run the trim cycle on a specific PR (after the watcher detects an event)
pr-review-trim:
	@if [ ! -f $(PR_TRIMMER) ]; then echo "error: $(PR_TRIMMER) not found"; exit 2; fi
	python $(PR_TRIMMER) $(PR)
