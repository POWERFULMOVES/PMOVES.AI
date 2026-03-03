#!/usr/bin/env python3
"""Model & Persona Readiness Check for PMOVES.AI

Validates that the model registry, persona seeds, and model providers
are correctly configured and reachable at startup.

Checks:
  1. Supabase model_providers - all active providers have valid config
  2. Supabase personas - table populated with >=8 rows
  3. Ollama /api/tags - expected local models are pulled
  4. TensorZero /v1/models - gateway operational
  5. Persona-model resolution - all personas resolve to valid models

Exit codes:
  0 = all checks pass
  1 = one or more checks failed

Usage:
  python tools/model_readiness_check.py [--supabase-url URL] [--ollama-url URL] [--tensorzero-url URL]
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PERSONA_MODEL_PREFERENCES: set[str] = {
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-haiku-4-5",
}

CRITICAL_OLLAMA_MODELS: tuple[str, ...] = ("qwen3", "nomic-embed-text")
MIN_ACTIVE_MODELS = 35
MIN_SERVICE_MODEL_MAPPINGS = 15
DOCKER_PROXY_CONTAINER = os.environ.get("MODEL_READINESS_DOCKER_PROXY", "pmoves-archon-1")
DOCKER_DB_CONTAINER = os.environ.get("MODEL_READINESS_DB_CONTAINER", "pmoves-supabase-db-1")
_DOCKER_PROXY_AVAILABLE: bool | None = None
_DOCKER_DB_AVAILABLE: bool | None = None


def _is_allowed_scheme(url: str) -> bool:
    """Allow only HTTP(S) URLs for outbound readiness probes."""
    return urllib.parse.urlparse(url).scheme in {"http", "https"}


def _normalize_supabase_base(url: str) -> str:
    """Normalize Supabase URL so callers can append /rest/v1 paths consistently."""
    raw = (url or "").strip().rstrip("/")
    if raw.endswith("/rest/v1"):
        return raw[: -len("/rest/v1")]
    return raw


def _rewrite_for_compose_proxy(url: str) -> str:
    """Map host-only endpoints to in-network service URLs for docker-exec fallback."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "host.docker.internal"}:
        return url

    port = parsed.port
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""

    if port in {54321, 65421, 3010, 8000, 3000} or path.startswith("/rest/v1"):
        rewritten_path = path
        if rewritten_path.startswith("/rest/v1/"):
            rewritten_path = rewritten_path[len("/rest/v1"):]
        elif rewritten_path == "/rest/v1":
            rewritten_path = "/"
        return f"http://supabase-postgrest:3000{rewritten_path}{query}"
    if port == 11434:
        return f"http://pmoves-ollama:11434{path}{query}"
    if port == 3030:
        return f"http://tensorzero-gateway:3000{path}{query}"
    return url


def _docker_proxy_available() -> bool:
    """Check once whether docker proxy container exists and is runnable."""
    global _DOCKER_PROXY_AVAILABLE
    if _DOCKER_PROXY_AVAILABLE is not None:
        return _DOCKER_PROXY_AVAILABLE
    try:
        result = subprocess.run(
            ["docker", "inspect", DOCKER_PROXY_CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        _DOCKER_PROXY_AVAILABLE = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        _DOCKER_PROXY_AVAILABLE = False
    return _DOCKER_PROXY_AVAILABLE


def _docker_db_available() -> bool:
    """Check once whether Supabase DB container exists and is runnable."""
    global _DOCKER_DB_AVAILABLE
    if _DOCKER_DB_AVAILABLE is not None:
        return _DOCKER_DB_AVAILABLE
    try:
        result = subprocess.run(
            ["docker", "inspect", DOCKER_DB_CONTAINER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        _DOCKER_DB_AVAILABLE = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        _DOCKER_DB_AVAILABLE = False
    return _DOCKER_DB_AVAILABLE


def _db_query_rows(sql: str) -> list[str] | None:
    """Run SQL in Supabase DB container and return non-empty output rows."""
    if not _docker_db_available():
        return None
    cmd = [
        "docker", "exec", DOCKER_DB_CONTAINER,
        "psql", "-U", "postgres", "-d", "postgres", "-At",
        "-c", sql,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return lines


def _docker_http_raw(url: str, timeout: int = 10, key: str = "", schema: str = "") -> tuple[int, str] | None:
    """Fallback HTTP probe via docker exec in compose network."""
    if not _docker_proxy_available():
        return None

    rewritten = _rewrite_for_compose_proxy(url)
    cmd = [
        "docker", "exec",
        "-e", f"MR_URL={rewritten}",
        "-e", f"MR_KEY={key}",
        "-e", f"MR_SCHEMA={schema}",
        "-e", f"MR_TIMEOUT={timeout}",
        DOCKER_PROXY_CONTAINER,
        "sh", "-lc",
        'if [ -n "$MR_KEY" ]; then '
        'if [ -n "$MR_SCHEMA" ]; then prof="-H Accept-Profile:$MR_SCHEMA -H Content-Profile:$MR_SCHEMA"; else prof=""; fi; '
        'curl -sS -m "$MR_TIMEOUT" -H "Accept: application/json" -H "apikey: $MR_KEY" -H "Authorization: Bearer $MR_KEY" $prof -w "\\n__PM_HTTP:%{http_code}" "$MR_URL"; '
        "else "
        'curl -sS -m "$MR_TIMEOUT" -H "Accept: application/json" -w "\\n__PM_HTTP:%{http_code}" "$MR_URL"; '
        "fi",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout + 5)
    except (OSError, subprocess.SubprocessError):
        return None

    raw = (proc.stdout or "").strip()
    if "__PM_HTTP:" not in raw:
        return None
    body, _, status_part = raw.rpartition("__PM_HTTP:")
    try:
        code = int(status_part.strip())
    except ValueError:
        return None
    if code <= 0:
        return None
    return code, body.strip()


def http_get(url: str, timeout: int = 10) -> dict | None:
    """GET request returning parsed JSON or None on failure."""
    raw = http_get_raw(url, timeout=timeout)
    if raw is None:
        return None
    _, body = raw
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def http_get_raw(url: str, timeout: int = 10) -> tuple[int, str] | None:
    """GET request returning (status_code, text_body) or None on failure."""
    if not _is_allowed_scheme(url):
        return None
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode(errors="replace")
            return int(getattr(resp, "status", 200)), body
    except (urllib.error.URLError, OSError):
        return _docker_http_raw(url, timeout=timeout)


def http_get_supabase(url: str, key: str, timeout: int = 10, schema: str = "pmoves_core") -> dict | list | None:
    """GET request with Supabase anon key auth."""
    if not _is_allowed_scheme(url):
        return None
    try:
        headers = {
            "Accept": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        if schema:
            headers["Accept-Profile"] = schema
            headers["Content-Profile"] = schema
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        raw = _docker_http_raw(url, timeout=timeout, key=key, schema=schema)
        if raw is None:
            return None
        code, body = raw
        if code >= 400:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None


class ReadinessChecker:
    def __init__(self, supabase_url: str, supabase_key: str,
                 ollama_url: str, tensorzero_url: str, strict_ollama: bool = False) -> None:
        """Store service endpoints and counters for a readiness run."""
        self.supabase_url = _normalize_supabase_base(supabase_url).rstrip("/")
        self.supabase_key = supabase_key
        self.ollama_url = ollama_url.rstrip("/")
        self.tensorzero_url = tensorzero_url.rstrip("/")
        self.strict_ollama = strict_ollama
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def _check(self, name: str, ok: bool, detail: str = "") -> None:
        """Record and print a pass/fail check result."""
        status = "PASS" if ok else "FAIL"
        icon = "+" if ok else "!"
        msg = f"  [{icon}] {name}: {status}"
        if detail:
            msg += f" - {detail}"
        print(msg)
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def _warn(self, name: str, detail: str = "") -> None:
        """Record and print a non-fatal warning."""
        print(f"  [~] {name}: WARN - {detail}")
        self.warnings += 1

    def check_supabase_providers(self) -> None:
        """Check model_providers table is populated."""
        print("\n[1] Supabase model_providers")
        url = f"{self.supabase_url}/rest/v1/model_providers?select=name,type,active&active=eq.true"
        data = http_get_supabase(url, self.supabase_key)
        if data is None:
            rows = _db_query_rows("select name, type from pmoves_core.model_providers where active = true;")
            if rows is None:
                self._check("Supabase reachable", False, f"cannot reach {self.supabase_url}")
                return
            self._check("Supabase reachable", True, f"db fallback via {DOCKER_DB_CONTAINER}")
            names = {row.split("|", 1)[0].strip() for row in rows}
            self._check("Providers populated", len(rows) >= 8,
                        f"{len(rows)} active providers (need >=8: ollama, anthropic, openai, etc.)")
            self._check("Anthropic provider exists", "anthropic_primary" in names,
                        "anthropic_primary" + (" found" if "anthropic_primary" in names else " MISSING"))
            self._check("TTS provider exists", "tts_local" in names,
                        "tts_local" + (" found" if "tts_local" in names else " MISSING"))

            models_rows = _db_query_rows("select count(*) from pmoves_core.models where active = true;")
            if not models_rows:
                self._check("Models table reachable", False, "cannot query pmoves_core.models")
            else:
                model_count = int(models_rows[0])
                self._check("Models seeded", model_count >= MIN_ACTIVE_MODELS,
                            f"{model_count} active models (need >={MIN_ACTIVE_MODELS})")

            mapping_rows = _db_query_rows("select count(*) from pmoves_core.service_model_mappings;")
            if not mapping_rows:
                self._check("Service-model mappings reachable", False,
                            "cannot query pmoves_core.service_model_mappings")
            else:
                mapping_count = int(mapping_rows[0])
                self._check("Service-model mappings seeded",
                            mapping_count >= MIN_SERVICE_MODEL_MAPPINGS,
                            f"{mapping_count} mappings (need >={MIN_SERVICE_MODEL_MAPPINGS})")
            return

        count = len(data) if isinstance(data, list) else 0
        self._check("Providers populated", count >= 8,
                     f"{count} active providers (need >=8: ollama, anthropic, openai, etc.)")

        # Check for Anthropic specifically
        names = {p.get("name") for p in data} if isinstance(data, list) else set()
        self._check("Anthropic provider exists", "anthropic_primary" in names,
                     "anthropic_primary" + (" found" if "anthropic_primary" in names else " MISSING"))

        # Check for TTS provider
        self._check("TTS provider exists", "tts_local" in names,
                     "tts_local" + (" found" if "tts_local" in names else " MISSING"))

        # Check model registry size threshold
        models_url = f"{self.supabase_url}/rest/v1/models?select=id&active=eq.true"
        models_data = http_get_supabase(models_url, self.supabase_key)
        if not isinstance(models_data, list):
            self._check("Models table reachable", False, "cannot query /rest/v1/models")
        else:
            self._check("Models seeded", len(models_data) >= MIN_ACTIVE_MODELS,
                        f"{len(models_data)} active models (need >={MIN_ACTIVE_MODELS})")

        # Check service-model mapping threshold (table has no active flag)
        mappings_url = f"{self.supabase_url}/rest/v1/service_model_mappings?select=id"
        mappings_data = http_get_supabase(mappings_url, self.supabase_key)
        if not isinstance(mappings_data, list):
            self._check("Service-model mappings reachable", False,
                        "cannot query /rest/v1/service_model_mappings")
        else:
            self._check("Service-model mappings seeded",
                        len(mappings_data) >= MIN_SERVICE_MODEL_MAPPINGS,
                        f"{len(mappings_data)} mappings (need >={MIN_SERVICE_MODEL_MAPPINGS})")

    def check_supabase_personas(self) -> None:
        """Check personas table has >=8 rows."""
        print("\n[2] Supabase personas")
        url = f"{self.supabase_url}/rest/v1/personas?select=name,model_preference,is_active&is_active=eq.true"
        data = http_get_supabase(url, self.supabase_key)
        if data is None:
            rows = _db_query_rows("select name, model_preference from pmoves_core.personas where is_active = true;")
            if rows is None:
                self._check("Personas table reachable", False,
                            f"cannot query personas at {self.supabase_url}")
                return
            count = len(rows)
            self._check("Personas populated", count >= 8,
                        f"{count} active personas (need >=8)")
            models = {row.split("|", 1)[1].strip() for row in rows if "|" in row}
            missing = PERSONA_MODEL_PREFERENCES - models
            self._check("Persona model preferences valid",
                        len(missing) == 0,
                        f"missing model refs: {missing}" if missing else "all 3 Claude models referenced")
            return

        count = len(data) if isinstance(data, list) else 0
        self._check("Personas populated", count >= 8,
                     f"{count} active personas (need >=8)")

        if isinstance(data, list) and count > 0:
            models = {p.get("model_preference") for p in data}
            missing = PERSONA_MODEL_PREFERENCES - models
            self._check("Persona model preferences valid",
                         len(missing) == 0,
                         f"missing model refs: {missing}" if missing else "all 3 Claude models referenced")

    def check_ollama(self) -> None:
        """Check Ollama has expected local models pulled."""
        print("\n[3] Ollama local models")
        data = http_get(f"{self.ollama_url}/api/tags")
        if data is None:
            self._check("Ollama reachable", False, f"cannot reach {self.ollama_url}")
            return

        models = data.get("models", [])
        pulled_base = {m.get("name", "").split(":")[0].strip().lower() for m in models if m.get("name")}
        self._check("Ollama responding", True, f"{len(models)} models loaded")

        # Check critical models
        for model in CRITICAL_OLLAMA_MODELS:
            found = model.strip().lower() in pulled_base
            if not found and self.strict_ollama:
                self._check(f"Model '{model}'", False, "not pulled")
            elif not found:
                self._warn(f"Model '{model}'", "not pulled")
            else:
                self._check(f"Model '{model}'", True, "available")

    def check_tensorzero(self) -> None:
        """Check TensorZero gateway is operational."""
        print("\n[4] TensorZero gateway")
        # TensorZero doesn't always return JSON on health/root; use HTTP success for reachability.
        data = http_get_raw(f"{self.tensorzero_url}/health")
        if data is not None:
            self._check("TensorZero health", True, "gateway responding")
            return

        # Fallback: try root
        data = http_get_raw(self.tensorzero_url)
        if data is not None:
            self._check("TensorZero reachable", True, "gateway responding (root)")
        else:
            self._check("TensorZero reachable", False, f"cannot reach {self.tensorzero_url}")

    def check_persona_resolution(self) -> None:
        """Check persona_model_resolution view returns valid data."""
        print("\n[5] Persona-model resolution")
        url = (f"{self.supabase_url}/rest/v1/persona_model_resolution"
               f"?select=persona_name,model_preference,provider_name,persona_active"
               f"&persona_active=eq.true")
        data = http_get_supabase(url, self.supabase_key)

        if data is None:
            rows = _db_query_rows(
                "select persona_name, model_preference, provider_name "
                "from pmoves_core.persona_model_resolution where persona_active = true;"
            )
            if rows is None:
                self._check("Resolution view reachable", False, "view missing or query failed")
                return
            unresolved = [row for row in rows if row.endswith("|") or row.split("|")[-1].strip() == ""]
            self._check("Resolution view populated", len(rows) >= 8, f"{len(rows)} resolved personas")
            self._check("All personas resolve to providers",
                        len(unresolved) == 0,
                        f"{len(unresolved)} unresolved" if unresolved else "all resolved")
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
        else:
            self._check("Resolution payload format", False,
                        f"expected JSON array, got {type(data).__name__}")

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


def main() -> None:
    default_supabase = (
        os.environ.get("MODEL_READINESS_SUPABASE_URL")
        or os.environ.get("SUPABASE_REST_URL")
        or os.environ.get("SUPA_REST_URL")
        or os.environ.get("SUPABASE_URL")
        or "http://localhost:3010"
    )
    default_supabase_key = (
        os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("ANON_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SERVICE_ROLE_KEY")
        or ""
    )
    default_ollama = (
        os.environ.get("OLLAMA_URL")
        or os.environ.get("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    )
    default_tensorzero = (
        os.environ.get("TENSORZERO_URL")
        or os.environ.get("TENSORZERO_BASE_URL")
        or "http://localhost:3030"
    )
    default_strict_ollama = os.environ.get("MODEL_READINESS_STRICT_OLLAMA", "0").strip().lower() in {"1", "true", "yes", "on"}

    parser = argparse.ArgumentParser(description="Model & Persona Readiness Check")
    parser.add_argument("--supabase-url",
                        default=default_supabase,
                        help="Supabase PostgREST URL (default: $SUPABASE_URL or localhost:3010)")
    parser.add_argument("--supabase-key",
                        default=default_supabase_key,
                        help="Supabase anon key (default: $SUPABASE_ANON_KEY)")
    parser.add_argument("--ollama-url",
                        default=default_ollama,
                        help="Ollama API URL (default: $OLLAMA_URL or localhost:11434)")
    parser.add_argument("--tensorzero-url",
                        default=default_tensorzero,
                        help="TensorZero gateway URL (default: $TENSORZERO_URL or localhost:3030)")
    parser.add_argument("--strict-ollama",
                        action="store_true",
                        default=default_strict_ollama,
                        help="Fail when critical Ollama models are missing (default: warn only)")
    args = parser.parse_args()

    if not args.supabase_key:
        print("WARNING: no Supabase key set - Supabase checks will fail")
        print("  Set via: export SUPABASE_ANON_KEY=<key>")
        print("  Or set: export SUPABASE_SERVICE_ROLE_KEY=<key>")
        print("  Or pass: --supabase-key <key>\n")

    checker = ReadinessChecker(
        supabase_url=args.supabase_url,
        supabase_key=args.supabase_key,
        ollama_url=args.ollama_url,
        tensorzero_url=args.tensorzero_url,
        strict_ollama=args.strict_ollama,
    )
    sys.exit(checker.run())


if __name__ == "__main__":
    main()
