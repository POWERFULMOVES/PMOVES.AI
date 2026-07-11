# mk/voice.mk — Known-Road wrappers for the standalone voice deploy units.
#
# Both composes are named *.compose.yml (NOT docker-compose*.yml) so they live
# OUTSIDE the damage-control compose-Known-Road glob and can be committed files.
# These make targets are the SANCTIONED way to run them — never invoke
# `docker compose -f ...compose.yml` by hand (that is the work-around this file
# replaces). Two units:
#   * kokoro-tts     — CPU-only, GPU-less voice on a KVM (#2024)
#   * omnivoice      — GPU production voice server (SPARK target; 4090 x86 validated)

# ---------------------------------------------------------------------------
# Kokoro CPU TTS (#2024) — "it's time for agents to start talking" on cheap nodes
# ---------------------------------------------------------------------------
KOKORO_COMPOSE := services/kokoro-tts/kokoro.compose.yml
KOKORO_DC      := docker compose -f $(KOKORO_COMPOSE)
KOKORO_PORT    := $${KOKORO_HOST_PORT:-8004}
KOKORO_MODEL_URL  := https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
KOKORO_VOICES_URL := https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

kokoro-digests: ## Compute + print the pinned Kokoro model/voices sha256 build args (pin these in CI once)
	@echo "KOKORO_MODEL_SHA256=$$(curl -fsSL $(KOKORO_MODEL_URL) | sha256sum | cut -d' ' -f1)"
	@echo "KOKORO_VOICES_SHA256=$$(curl -fsSL $(KOKORO_VOICES_URL) | sha256sum | cut -d' ' -f1)"

kokoro-build: ## Build the Kokoro CPU image (needs KOKORO_MODEL_SHA256+KOKORO_VOICES_SHA256 — see kokoro-digests, or use kokoro-smoke)
	@test -n "$$KOKORO_MODEL_SHA256" && test -n "$$KOKORO_VOICES_SHA256" || { \
	  echo "Set KOKORO_MODEL_SHA256 + KOKORO_VOICES_SHA256 (make kokoro-digests) or run 'make kokoro-smoke'"; exit 1; }
	@$(KOKORO_DC) --profile voice build kokoro-tts

kokoro-up: ## Start the Kokoro CPU TTS service (127.0.0.1:8004 by default)
	@$(KOKORO_DC) --profile voice up -d kokoro-tts
	@echo "✅ kokoro-tts up. Health: http://localhost:$(KOKORO_PORT)/healthz"

kokoro-down: ## Stop + remove the Kokoro service
	@$(KOKORO_DC) --profile voice down

kokoro-logs: ## Tail the Kokoro service logs
	@$(KOKORO_DC) --profile voice logs -f --tail 60 kokoro-tts

kokoro-smoke: ## One-shot: pin digests → build → run → synthesize a sample WAV to out/kokoro-smoke.wav (hear the CPU voice)
	@set -e; \
	echo "[1/4] Pinning model digests (hashing the release assets)…"; \
	m=$$(curl -fsSL $(KOKORO_MODEL_URL)  | sha256sum | cut -d' ' -f1); \
	v=$$(curl -fsSL $(KOKORO_VOICES_URL) | sha256sum | cut -d' ' -f1); \
	echo "    model=$$m"; echo "    voices=$$v"; \
	echo "[2/4] Building image (bakes the pinned model, fail-closed on digest)…"; \
	KOKORO_MODEL_SHA256=$$m KOKORO_VOICES_SHA256=$$v $(KOKORO_DC) --profile voice build kokoro-tts; \
	echo "[3/4] Starting service + waiting for health…"; \
	KOKORO_MODEL_SHA256=$$m KOKORO_VOICES_SHA256=$$v $(KOKORO_DC) --profile voice up -d kokoro-tts; \
	for i in $$(seq 1 40); do curl -fsS localhost:$(KOKORO_PORT)/healthz >/dev/null 2>&1 && break || sleep 3; done; \
	curl -fsS localhost:$(KOKORO_PORT)/healthz; echo; \
	echo "[4/4] Synthesizing sample → out/kokoro-smoke.wav…"; \
	mkdir -p out; \
	curl -fsS -X POST localhost:$(KOKORO_PORT)/synthesize \
	  -H 'content-type: application/json' \
	  -d '{"text":"PMOVES agents are online.","voice":"af_heart"}' -o out/kokoro-smoke.wav; \
	echo "✅ Wrote out/kokoro-smoke.wav ($$(wc -c < out/kokoro-smoke.wav) bytes) — play it to hear the voice."

# ---------------------------------------------------------------------------
# OmniVoice GPU TTS — production voice server (k2-fsa/OmniVoice, Apache-2.0).
# build/up/down Known Roads already live in the main Makefile (OMNIVOICE section);
# this adds only the missing "hear it" smoke, reusing those targets so there is
# ONE compose invocation path. OMNIVOICE_COMPOSE is defined by the Makefile.
# ---------------------------------------------------------------------------
OMNIVOICE_PORT := $${OMNIVOICE_HOST_PORT:-8002}

omnivoice-smoke: ## Reuse omnivoice-build+up, then synthesize a sample WAV to out/omnivoice-smoke.wav (GPU; first run downloads k2-fsa/OmniVoice)
	@set -e; \
	echo "[1/3] Building GPU image via omnivoice-build (torch cu128 — several GB on first build)…"; \
	$(MAKE) --no-print-directory omnivoice-build; \
	echo "[2/3] Starting server via omnivoice-up (first run downloads the model — be patient)…"; \
	$(MAKE) --no-print-directory omnivoice-up; \
	echo "    waiting for health…"; \
	for i in $$(seq 1 60); do curl -fsS localhost:$(OMNIVOICE_PORT)/healthz >/dev/null 2>&1 && break || sleep 5; done; \
	curl -fsS localhost:$(OMNIVOICE_PORT)/healthz; echo; \
	echo "[3/3] Synthesizing sample → out/omnivoice-smoke.wav…"; \
	mkdir -p out; \
	tok=$${OMNIVOICE_TOKEN:-}; \
	curl -fsS -X POST localhost:$(OMNIVOICE_PORT)/synthesize \
	  $${tok:+-H "X-OmniVoice-Token: $$tok"} \
	  -H 'content-type: application/json' \
	  -d '{"text":"PMOVES agents are online."}' -o out/omnivoice-smoke.wav; \
	echo "✅ Wrote out/omnivoice-smoke.wav ($$(wc -c < out/omnivoice-smoke.wav) bytes) — play it to hear OmniVoice."

.PHONY: kokoro-digests kokoro-build kokoro-up kokoro-down kokoro-logs kokoro-smoke \
        omnivoice-smoke

# ---------------------------------------------------------------------------
# CHIT-sign -> expressive voice loop (Phase 0). tools/voice_cast_on_sign.py
# subscribes to agent.graphiti.signed.v1 and turns an agent's normal
# sign_trail (CHIT_SIGN_PUBLISH=1) into an audible, persona-shaped utterance via
# Flute-Gateway -- NO speak tool call. Runs on the HOST (winsound/aplay playback;
# the daemon translates Docker-internal NATS URLs back to localhost, so it must
# not run inside the compose network). Requires the voice stack up (make up-voice)
# and nats-1 host-published on 4222 (auth nats:pmoves).
# ---------------------------------------------------------------------------
VOICE_CAST_PID  := out/.voice-cast.pid
VOICE_CAST_LOG  := out/voice-cast.log
# 127.0.0.1 (not localhost): on Windows `localhost` resolves to IPv6 ::1 first, but
# Docker publishes nats :4222 on IPv4 only -> an IPv6 connect hangs/times out.
VOICE_CAST_NATS ?= nats://nats:pmoves@127.0.0.1:4222

voice-cast-deps: ## Ensure host python deps (nats-py, httpx) for the CHIT-sign voice subscriber
	@python -c "import nats"  2>/dev/null || python -m pip install --quiet --disable-pip-version-check nats-py
	@python -c "import httpx" 2>/dev/null || python -m pip install --quiet --disable-pip-version-check httpx

voice-cast-up: voice-cast-deps ## Start the CHIT-sign -> expressive voice subscriber (Phase 0; reads FLUTE_API_KEY from the running flute-gateway)
	@mkdir -p out
	@if [ -f $(VOICE_CAST_PID) ] && kill -0 $$(cat $(VOICE_CAST_PID)) 2>/dev/null; then \
	  echo "voice-cast-on-sign already running (pid $$(cat $(VOICE_CAST_PID)))"; exit 0; fi
	@key="$$(docker exec pmoves-flute-gateway-1 printenv FLUTE_API_KEY 2>/dev/null)"; \
	 VOICE_CAST_NATS_URL="$(VOICE_CAST_NATS)" \
	 FLUTE_GATEWAY_URL="http://localhost:8055" \
	 FLUTE_API_KEY="$$key" \
	 nohup python tools/voice_cast_on_sign.py > $(VOICE_CAST_LOG) 2>&1 & echo $$! > $(VOICE_CAST_PID)
	@sleep 3; echo "voice-cast-on-sign started (pid $$(cat $(VOICE_CAST_PID))) -- log: pmoves/$(VOICE_CAST_LOG)"; \
	 grep -q "connected to" $(VOICE_CAST_LOG) 2>/dev/null && echo "  NATS connected [OK]" || { echo "  [warn] not connected yet -- tail:"; tail -3 $(VOICE_CAST_LOG); }

voice-cast-down: ## Stop the CHIT-sign voice subscriber
	@if [ -f $(VOICE_CAST_PID) ]; then kill $$(cat $(VOICE_CAST_PID)) 2>/dev/null; rm -f $(VOICE_CAST_PID); echo "voice-cast-on-sign stopped"; else echo "voice-cast-on-sign not running"; fi

voice-cast-smoke: voice-cast-deps ## Fire a CHIT sign (mr-clean) and confirm an expressive utterance is cast to out/
	@echo "Publishing a signed CHIT trail (agent.graphiti.signed.v1)..."
	@before="$$(ls -1 out/voice_cast_*.wav 2>/dev/null | wc -l)"; \
	 CHIT_SIGN_PUBLISH=1 NATS_URL="$(VOICE_CAST_NATS)" PYTHONPATH="$(CURDIR)/.." \
	   python tools/sign_trail.py --agent-id 4090-claude --alter mr-clean \
	   --summary "Powerful moves. The CHIT sign is now my voice." --phase "Phase 0" >/dev/null || true; \
	 echo "  waiting for the cast..."; \
	 for i in $$(seq 1 25); do \
	   after="$$(ls -1 out/voice_cast_*.wav 2>/dev/null | wc -l)"; \
	   if [ "$$after" -gt "$$before" ]; then \
	     f="$$(ls -t out/voice_cast_*.wav | head -1)"; \
	     echo "[OK] cast: pmoves/$$f ($$(wc -c < $$f) bytes) -- play it to hear the CHIT sign as expressive voice"; exit 0; fi; \
	   sleep 1; \
	 done; \
	 echo "[warn] no new cast WAV after 25s -- check pmoves/$(VOICE_CAST_LOG)"; tail -8 $(VOICE_CAST_LOG) 2>/dev/null; exit 1

.PHONY: voice-cast-deps voice-cast-up voice-cast-down voice-cast-smoke
