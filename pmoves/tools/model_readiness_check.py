#!/usr/bin/env python3
"""Model & Persona Readiness Check for PMOVES.AI

Validates that the model registry, persona seeds, and model providers
are correctly configured and reachable at startup.

Checks:
  1. Supabase model_providers — all active providers have valid config
  2. Supabase personas — table populated with ≥8 rows
  3. Ollama /api/tags — expected local models are pulled
  4. TensorZero /v1/models — gateway operational
  5. Persona-model resolution — all personas resolve to valid models

Exit codes:
  0 = all checks pass
  1 = one or more checks failed

Usage:
  python tools/model_readiness_check.py [--supabase-url URL] [--ollama-url URL] [--tensorzero-url URL]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def http_get(url: str, timeout: int = 10) -> dict | None:
    """GET request returning parsed JSON or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def http_get_supabase(url: str, key: str, timeout: int = 10) -> dict | list | None:
    """GET request with Supabase anon key auth."""
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


class ReadinessChecker:
    def __init__(self, supabase_url: str, supabase_key: str,
                 ollama_url: str, tensorzero_url: str):
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self.ollama_url = ollama_url.rstrip("/")
        self.tensorzero_url = tensorzero_url.rstrip("/")
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def _check(self, name: str, ok: bool, detail: str = ""):
        status = "PASS" if ok else "FAIL"
        icon = "+" if ok else "!"
        msg = f"  [{icon}] {name}: {status}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def _warn(self, name: str, detail: str = ""):
        print(f"  [~] {name}: WARN — {detail}")
        self.warnings += 1

    def check_supabase_providers(self) -> None:
        """Check model_providers table is populated."""
        print("\n[1] Supabase model_providers")
        url = f"{self.supabase_url}/rest/v1/model_providers?select=name,type,active&active=eq.true"
        data = http_get_supabase(url, self.supabase_key)
        if data is None:
            self._check("Supabase reachable", False, f"cannot reach {self.supabase_url}")
            return

        count = len(data) if isinstance(data, list) else 0
        self._check("Providers populated", count >= 8,
                     f"{count} active providers (need ≥8: ollama, anthropic, openai, etc.)")

        # Check for Anthropic specifically
        names = {p.get("name") for p in data} if isinstance(data, list) else set()
        self._check("Anthropic provider exists", "anthropic_primary" in names,
                     "anthropic_primary" + (" found" if "anthropic_primary" in names else " MISSING"))

        # Check for TTS provider
        self._check("TTS provider exists", "tts_local" in names,
                     "tts_local" + (" found" if "tts_local" in names else " MISSING"))

    def check_supabase_personas(self) -> None:
        """Check personas table has ≥8 rows."""
        print("\n[2] Supabase personas")
        url = f"{self.supabase_url}/rest/v1/personas?select=name,model_preference,is_active&is_active=eq.true"
        data = http_get_supabase(url, self.supabase_key)
        if data is None:
            self._check("Personas table reachable", False,
                         f"cannot query personas at {self.supabase_url}")
            return

        count = len(data) if isinstance(data, list) else 0
        self._check("Personas populated", count >= 8,
                     f"{count} active personas (need ≥8)")

        if isinstance(data, list) and count > 0:
            models = {p.get("model_preference") for p in data}
            expected = {"claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"}
            missing = expected - models
            self._check("Persona model preferences valid",
                         len(missing) == 0,
                         f"missing model refs: {missing}" if missing else "all 3 Claude models referenced")

    def check_ollama(self) -> None:
        """Check Ollama has expected local models pulled."""
        print("\n[3] Ollama local models")
        data = http_get(f"{self.ollama_url}/api/tags")
        if data is None:
            self._warn("Ollama reachable", f"cannot reach {self.ollama_url} (may not be running)")
            return

        models = data.get("models", [])
        pulled = {m.get("name", "").split(":")[0] for m in models}
        self._check("Ollama responding", True, f"{len(models)} models loaded")

        # Check critical models
        critical = ["qwen3", "nomic-embed-text"]
        for model in critical:
            found = any(model in name for name in pulled)
            if not found:
                self._warn(f"Model '{model}'", "not pulled (may need: ollama pull)")
            else:
                self._check(f"Model '{model}'", True, "available")

    def check_tensorzero(self) -> None:
        """Check TensorZero gateway is operational."""
        print("\n[4] TensorZero gateway")
        # TensorZero doesn't have a /v1/models endpoint like OpenAI
        # Check if the service responds at all
        data = http_get(f"{self.tensorzero_url}/health")
        if data is not None:
            self._check("TensorZero health", True, "gateway responding")
            return

        # Fallback: try root
        data = http_get(self.tensorzero_url)
        if data is not None:
            self._check("TensorZero reachable", True, "gateway responding (root)")
        else:
            self._warn("TensorZero reachable",
                        f"cannot reach {self.tensorzero_url} (may not be running)")

    def check_persona_resolution(self) -> None:
        """Check persona_model_resolution view returns valid data."""
        print("\n[5] Persona-model resolution")
        url = (f"{self.supabase_url}/rest/v1/persona_model_resolution"
               f"?select=persona_name,model_preference,provider_name,persona_active"
               f"&persona_active=eq.true")
        data = http_get_supabase(url, self.supabase_key)

        if data is None:
            self._warn("Resolution view", "view may not exist yet (run migration first)")
            return

        if isinstance(data, list):
            count = len(data)
            unresolved = [p for p in data if p.get("provider_name") is None]
            self._check("Resolution view populated", count >= 8,
                         f"{count} resolved personas")
            self._check("All personas resolve to providers",
                         len(unresolved) == 0,
                         f"{len(unresolved)} unresolved" if unresolved else "all resolved")
            if unresolved:
                for p in unresolved:
                    self._warn(f"  Unresolved: {p.get('persona_name')}",
                               f"model_preference={p.get('model_preference')}")

    def run(self) -> int:
        """Run all checks and return exit code."""
        print("=" * 60)
        print("PMOVES.AI Model & Persona Readiness Check")
        print("=" * 60)

        self.check_supabase_providers()
        self.check_supabase_personas()
        self.check_ollama()
        self.check_tensorzero()
        self.check_persona_resolution()

        print("\n" + "=" * 60)
        total = self.passed + self.failed
        print(f"Results: {self.passed}/{total} passed, "
              f"{self.failed} failed, {self.warnings} warnings")
        print("=" * 60)

        return 0 if self.failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Model & Persona Readiness Check")
    parser.add_argument("--supabase-url",
                        default=os.environ.get("SUPABASE_URL", "http://localhost:3010"),
                        help="Supabase PostgREST URL (default: $SUPABASE_URL or localhost:3010)")
    parser.add_argument("--supabase-key",
                        default=os.environ.get("SUPABASE_ANON_KEY", ""),
                        help="Supabase anon key (default: $SUPABASE_ANON_KEY)")
    parser.add_argument("--ollama-url",
                        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
                        help="Ollama API URL (default: $OLLAMA_URL or localhost:11434)")
    parser.add_argument("--tensorzero-url",
                        default=os.environ.get("TENSORZERO_URL", "http://localhost:3030"),
                        help="TensorZero gateway URL (default: $TENSORZERO_URL or localhost:3030)")
    args = parser.parse_args()

    if not args.supabase_key:
        print("WARNING: SUPABASE_ANON_KEY not set — Supabase checks will fail")
        print("  Set via: export SUPABASE_ANON_KEY=<key>")
        print("  Or pass: --supabase-key <key>\n")

    checker = ReadinessChecker(
        supabase_url=args.supabase_url,
        supabase_key=args.supabase_key,
        ollama_url=args.ollama_url,
        tensorzero_url=args.tensorzero_url,
    )
    sys.exit(checker.run())


if __name__ == "__main__":
    main()
