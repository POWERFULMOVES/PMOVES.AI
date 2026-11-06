"""Post-rotation provider-auth verification: does each provider ACCEPT its key?

The funnel can prove a credential is present (``secrets_sync``) and well-formed
(``secret_shape_rules``). Neither proves the provider accepts it, and after a
rotation that is the only question that matters. Before this tool there was no
auth smoke for Anthropic, OpenAI, Gemini or GHCR at all, and ``hf-mcp-health``
proves only that the HF MCP server is up -- not that ``HF_TOKEN`` works.

So: one cheap, authenticated, read-only request per credential, defined in
``pmoves/config/provider_auth_probes.yaml`` (model list or whoami). This is the
live half of the MiniMax Provider Verifier pattern (``provider_verifier_gate``
is its static half): config names the env var, never the key, and the live run
is the operator's step -- it is never run by CI or by an agent.

Output, per probe, is exactly: provider, credential label, HTTP status, and
ok / fail / unmeasured. Never the key, never a response body (a whoami body
can echo token metadata), never an exception message (only its class name).

Exit codes (pmoves/tools doctrine):
  0  every probe ok
  1  at least one probe FAILED auth (or failed its shape rule) -- actionable
  3  nothing failed, but at least one probe could not be measured
     (key absent, network error, 429/5xx, redirect, malformed config)
A missing key is unmeasured, never a pass. ``make`` collapses every non-zero
exit to 2, so the final ``VERDICT`` line is the observable result via make.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, field_validator, model_validator

from pmoves.tools.secret_shape import inspect_value
from pmoves.tools.secret_shape_rules import (
    DEFAULT_RULES_PATH,
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_UNMEASURED,
    LABEL_PATTERN,
    REPO_ROOT,
    RulesFileError,
    ShapeRule,
    format_validation_error,
    load_rules,
)

DEFAULT_PROBES_PATH = REPO_ROOT / "pmoves" / "config" / "provider_auth_probes.yaml"
USER_AGENT = "pmoves-secrets-provider-verify/1"
TIMEOUT_SECONDS = 15.0

Verdict = Literal["ok", "fail", "unmeasured"]

# Static headers live in a committed file, so none of them may be able to
# carry a credential. An ALLOWLIST, not a deny-list: a deny-list of
# auth-looking names still admitted `X-Access`, `Bearer` and `X-Session`.
# Adding a name here is a reviewed change to this file, which is the point.
STATIC_HEADER_ALLOWLIST = frozenset({
    "accept",
    "user-agent",
    "x-github-api-version",
    "anthropic-version",
})

# Machine-readable error reasons (google.rpc.ErrorInfo.reason, error.status):
# upper-snake identifiers only, so free-text messages are never retained.
_REASON_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MAX_ERROR_BODY = 65536


class ProbeConfigError(Exception):
    """The probes file is absent, unparseable, or fails the model. Exit 3."""


class RequireHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: StrictStr = Field(min_length=1)
    contains_any: Tuple[StrictStr, ...] = Field(min_length=1)


class ProviderProbe(BaseModel):
    """One read-only authenticated request. Holds an env-var NAME, never a key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    api_key_env: str = Field(pattern=LABEL_PATTERN)
    url: StrictStr
    auth_header: StrictStr = "Authorization"
    auth_scheme: StrictStr = "Bearer"
    headers: Dict[StrictStr, StrictStr] = Field(default_factory=dict)
    auth_failure_statuses: Tuple[int, ...] = (401, 403)
    # status -> reasons. A status listed here is an auth failure ONLY when the
    # error body's machine-readable reason is one of these; otherwise the
    # answer is unmeasured. Google answers a bad key with 400 + API_KEY_INVALID
    # but also answers 400 FAILED_PRECONDITION for an unsupported region.
    auth_failure_reasons: Dict[int, Tuple[StrictStr, ...]] = Field(default_factory=dict)
    # Token forms this probe cannot measure (e.g. an installation token cannot
    # call GET /user). Reported unmeasured, never sent.
    unmeasurable_prefixes: Tuple[StrictStr, ...] = ()
    require_header: Optional[RequireHeader] = None
    docs: Tuple[StrictStr, ...] = ()

    @field_validator("url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("probe url must be https:// -- a key is sent with it")
        return value

    @model_validator(mode="after")
    def _no_static_auth_bearing_header(self) -> "ProviderProbe":
        # Static headers are the one place a literal credential could be pasted
        # into this file. Only allowlisted, non-credential names may be set.
        for header in self.headers:
            if header.lower() not in STATIC_HEADER_ALLOWLIST:
                raise ValueError(
                    f"static header {header!r} is not in STATIC_HEADER_ALLOWLIST "
                    f"({', '.join(sorted(STATIC_HEADER_ALLOWLIST))})"
                )
        if self.auth_header.lower() in STATIC_HEADER_ALLOWLIST:
            raise ValueError(f"auth_header {self.auth_header!r} is an allowlisted static header")
        return self

    @model_validator(mode="after")
    def _reasons_are_coherent(self) -> "ProviderProbe":
        overlap = set(self.auth_failure_reasons) & set(self.auth_failure_statuses)
        if overlap:
            raise ValueError(
                f"status(es) {sorted(overlap)} are both unconditional and reason-gated"
            )
        for reasons in self.auth_failure_reasons.values():
            if not reasons or not all(_REASON_RE.match(r) for r in reasons):
                raise ValueError("auth_failure_reasons must be non-empty UPPER_SNAKE reasons")
        return self


class ProbeSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    probes: Tuple[ProviderProbe, ...]

    @model_validator(mode="after")
    def _names_unique(self) -> "ProbeSet":
        names = [p.name for p in self.probes]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate probe names: {', '.join(dupes)}")
        return self


def load_probes(path: Path | str = DEFAULT_PROBES_PATH) -> ProbeSet:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProbeConfigError(f"{path}: cannot read ({exc.__class__.__name__})") from None
    except yaml.YAMLError as exc:
        raise ProbeConfigError(f"{path}: not valid YAML ({exc.__class__.__name__})") from None
    try:
        return ProbeSet.model_validate(data)
    except ValidationError as exc:
        raise ProbeConfigError(
            f"{path}: probes file fails the model:\n  " + "\n  ".join(format_validation_error(exc))
        ) from None


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: Mapping[str, str]
    # Machine-readable error reasons only (see _error_reasons). Never a body.
    reasons: Tuple[str, ...] = ()


def _error_reasons(raw: bytes) -> Tuple[str, ...]:
    """Pull ``error.status`` and ``error.details[].reason`` out of an error body.

    Only UPPER_SNAKE identifiers survive, so a message that echoes anything --
    including the key -- cannot. The body itself is discarded by the caller.
    """
    try:
        error = json.loads(raw.decode("utf-8", errors="replace")).get("error")
    except Exception:
        return ()
    if not isinstance(error, dict):
        return ()
    found = [error.get("status")]
    details = error.get("details")
    if isinstance(details, list):
        found.extend(d.get("reason") for d in details if isinstance(d, dict))
    return tuple(r for r in found if isinstance(r, str) and _REASON_RE.match(r))


# (url, headers, timeout) -> HttpResult. Raises on transport failure.
HttpGet = Callable[[str, Mapping[str, str], float], HttpResult]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow: urllib re-sends request headers, credential included."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def urllib_get(url: str, headers: Mapping[str, str], timeout: float) -> HttpResult:
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            # The body is never read: it is not needed and may echo the token.
            return HttpResult(status=response.status, headers=dict(response.headers.items()))
    except urllib.error.HTTPError as exc:
        # 4xx/5xx and unfollowed 3xx arrive here; they are answers, not errors.
        status = exc.code
        response_headers = dict(exc.headers.items()) if exc.headers else {}
        reasons: Tuple[str, ...] = ()
        if status >= 400:
            try:
                reasons = _error_reasons(exc.read(_MAX_ERROR_BODY))
            except Exception:
                reasons = ()
        exc.close()
        return HttpResult(status=status, headers=response_headers, reasons=reasons)


@dataclass(frozen=True)
class ProbeResult:
    provider: str
    label: str
    status: str
    verdict: Verdict
    note: str = ""


def _header_value(headers: Mapping[str, str], name: str) -> Optional[str]:
    wanted = name.lower()
    for header, value in headers.items():
        if header.lower() == wanted:
            return value
    return None


def run_probe(
    probe: ProviderProbe,
    env: Mapping[str, str],
    rules: Mapping[str, ShapeRule],
    http_get: HttpGet,
    timeout: float = TIMEOUT_SECONDS,
) -> ProbeResult:
    label = probe.api_key_env

    def result(status: str, verdict: Verdict, note: str = "") -> ProbeResult:
        return ProbeResult(provider=probe.name, label=label, status=status, verdict=verdict, note=note)

    value = env.get(label, "")
    if not value.strip():
        return result("-", "unmeasured", "key not set in the loaded environment")

    # Never send a value the funnel would have withheld: a lookalike glyph
    # cannot go in a header at all, and a truncated key only buys a 401 that
    # says less than the shape finding does.
    rule = rules.get(label)
    if inspect_value(label, value).withhold or (rule is not None and rule.check(value)):
        return result("shape", "fail", "fails its shape rule -- run make -C pmoves secrets-shapes-check")

    if any(value.startswith(p) for p in probe.unmeasurable_prefixes):
        return result("-", "unmeasured", "this token form cannot be measured by this probe")

    credential = f"{probe.auth_scheme} {value}" if probe.auth_scheme else value
    headers = {"User-Agent": USER_AGENT, **probe.headers, probe.auth_header: credential}
    try:
        response = http_get(probe.url, headers, timeout)
    except Exception as exc:  # transport failure: report the class, never the message
        return result("-", "unmeasured", f"request failed ({exc.__class__.__name__})")

    status = str(response.status)
    if 200 <= response.status < 300:
        required = probe.require_header
        if required is not None:
            present = _header_value(response.headers, required.name) or ""
            granted = {scope.strip() for scope in present.split(",")}
            if not granted.intersection(required.contains_any):
                return result(
                    status, "fail",
                    f"authenticated, but {required.name} lacks any of "
                    + ", ".join(required.contains_any),
                )
        return result(status, "ok")
    if response.status in probe.auth_failure_statuses:
        return result(status, "fail", "provider rejected the credential")
    gated = probe.auth_failure_reasons.get(response.status)
    if gated is not None:
        matched = sorted(set(response.reasons) & set(gated))
        if matched:
            return result(status, "fail", f"provider rejected the credential ({matched[0]})")
        return result(status, "unmeasured", "error is not an auth rejection (e.g. region/precondition)")
    return result(status, "unmeasured", "neither accepted nor rejected (retry later)")


def run(
    probes: Sequence[ProviderProbe],
    env: Mapping[str, str],
    rules: Mapping[str, ShapeRule],
    http_get: HttpGet = urllib_get,
) -> List[ProbeResult]:
    return [run_probe(probe, env, rules, http_get) for probe in probes]


def exit_code(results: Sequence[ProbeResult]) -> int:
    verdicts = {r.verdict for r in results}
    if "fail" in verdicts:
        return EXIT_FINDINGS
    if "unmeasured" in verdicts or not results:
        return EXIT_UNMEASURED
    return EXIT_OK


_VERDICT_WORD = {EXIT_OK: "PASS", EXIT_FINDINGS: "FAIL", EXIT_UNMEASURED: "UNMEASURED"}


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None,
         http_get: HttpGet = urllib_get) -> int:
    parser = argparse.ArgumentParser(description="One read-only auth call per provider credential.")
    parser.add_argument("--probes", default=str(DEFAULT_PROBES_PATH))
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    parser.add_argument("--only", nargs="*", default=None, help="probe names to run (default: all)")
    parser.add_argument("--json", action="store_true", help="emit a JSON verdict on stdout")
    args = parser.parse_args(argv)

    try:
        probe_set = load_probes(args.probes)
        rules = load_rules(args.rules)
    except (ProbeConfigError, RulesFileError) as exc:
        print(f"secrets-provider-verify: COULD-NOT-MEASURE -- {exc}", file=sys.stderr)
        print("VERDICT: UNMEASURED exit=3")
        return EXIT_UNMEASURED

    probes = list(probe_set.probes)
    if args.only:
        unknown = sorted(set(args.only) - {p.name for p in probes})
        if unknown:
            print(f"secrets-provider-verify: unknown probe(s): {', '.join(unknown)}", file=sys.stderr)
            print("VERDICT: UNMEASURED exit=3")
            return EXIT_UNMEASURED
        probes = [p for p in probes if p.name in set(args.only)]

    results = run(probes, os.environ if env is None else env, rules, http_get)
    code = exit_code(results)
    if args.json:
        print(json.dumps({
            "verdict": _VERDICT_WORD[code],
            "checks": [asdict(r) for r in results],
            "summary": f"{sum(r.verdict == 'ok' for r in results)}/{len(results)} ok",
        }, indent=2))
    else:
        print(f"{'provider':<16} {'credential':<20} {'http':<6} verdict")
        for r in results:
            line = f"{r.provider:<16} {r.label:<20} {r.status:<6} {r.verdict}"
            print(line + (f"  ({r.note})" if r.note else ""))
    # stderr under --json so stdout stays one parseable document.
    print(f"VERDICT: {_VERDICT_WORD[code]} exit={code}", file=sys.stderr if args.json else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
