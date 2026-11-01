#!/usr/bin/env python3
"""gh_app_installation_audit.py — prove which registry repos the GitHub App
installation actually covers.

THE QUESTION
------------
The operator asked: "GH App installation state on the newly-scoped repos" and
got a 401 from the host. The App credentials (``GH_APP_ID``,
``GH_APP_CLIENT_ID``, ``GH_APP_INSTALLATION_ID``, ``GH_APP_SEC``) live only in
GitHub Actions secrets, so the answer cannot be produced from the operator's
laptop. This tool is the CI-side half: it reads the App's own installation and
reports, per repo, whether the installation covers it.

THE UNIVERSE IS DERIVED, NEVER ASSUMED
--------------------------------------
The repo universe comes from ``pmoves/config/fork_registry.json`` at runtime:
every entry under ``forks`` plus every entry under ``_first_party``. The
registry's ``_excluded`` map is reported separately, WITH its reason, and its
members are NOT part of the universe. The number of repos in the universe is
therefore whatever the registry says it is today — this tool computes it and
prints it, and never hardcodes it.

(Do not confuse the universe with the ``fork-sync.yml`` workflow's sync scope.
That is a SUBSET of the universe — the repos it auto-syncs — not the universe.)

THREE MODES, THREE DIFFERENT FAILURE POSTURES
---------------------------------------------
``--plan``      No network, no credentials. Derives the universe from the
                registry and prints it. This is how the universe size gets
                PROVEN rather than asserted, and it runs on the operator's
                host with nothing but Python.
``--token``     An installation token is already available (``GH_TOKEN`` or
                ``--token-file``). Reads ``GET /installation/repositories``.
``--app-jwt``   No installation token. Mints an App JWT with the house minter
                (``gh_app_token.build_app_jwt`` — RS256 via PyJWT, never a
                hand-rolled signer), lists the App's installations, picks the
                one for the registry's org, and reads that installation's
                repository list.

FAIL CLOSED — THE OPERATOR'S HARD RULE
--------------------------------------
"If the registry is unreadable/unparseable, or a GitHub API call errors, or
the response cannot be parsed, or pagination is incomplete, the tool must exit
NON-ZERO and must NOT emit a report that could be read as '0 repos missing'."

This tool keeps two things apart that are easy to conflate:

  * a FINDING   — "the App installation does not cover repo X". That is a real
    answer, and it is what the operator asked for.
  * an ABSENCE OF KNOWLEDGE — "we could not determine whether repo X is
    covered". That is a tool failure. It produces a non-zero exit, a report
    with ``complete: false``, and NO reassuring summary.

Every repo lands in exactly one of three buckets:

  installed      the installation covers it
  not_installed  the repo resolves in the org but the installation does NOT
                 cover it
  unknown        the repo name could not be resolved, so no claim is made
                 either way

The three bucket counts plus the total must equal the universe size. That
equality is asserted by the tool, not assumed by it.

SECRETS
-------
The installation token and the App JWT are never printed, never logged, never
written to the report — not even in a masked-but-partial form. Only metadata
(credential KIND, installation id, account login, endpoints) is emitted.

Exit codes:
  0  audit completed, coverage is fully determined
  2  usage / configuration error (bad arguments, missing credentials, the
     house JWT minter refused to load)
  3  the registry could not be read or parsed (instrument error)
  4  a GitHub API call failed, returned an unparseable body, or pagination
     could not be proven complete
  5  the bucket arithmetic did not close (instrument error)
  6  the audit is INCOMPLETE: at least one repo could not be resolved
  7  the audit completed and found repos the installation does not cover
     (only with --fail-on-not-installed)

Usage:
    python pmoves/tools/gh_app_installation_audit.py --plan
    python pmoves/tools/gh_app_installation_audit.py --plan --json
    python pmoves/tools/gh_app_installation_audit.py --token --json --out report.json
    python pmoves/tools/gh_app_installation_audit.py --app-jwt --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "pmoves" / "config" / "fork_registry.json"

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
USER_AGENT = "pmoves-gh-app-installation-audit"
SCHEMA = "pmoves.gh_app_installation_audit.v1"

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_REGISTRY = 3
EXIT_API = 4
EXIT_INVARIANT = 5
EXIT_INCOMPLETE = 6
EXIT_NOT_INSTALLED = 7

BUCKET_INSTALLED = "installed"
BUCKET_NOT_INSTALLED = "not_installed"
BUCKET_UNKNOWN = "unknown"
BUCKETS = (BUCKET_INSTALLED, BUCKET_NOT_INSTALLED, BUCKET_UNKNOWN)

# The one credential-free path: the installation's own repository list.
INSTALLATION_REPOSITORIES_PATH = "/installation/repositories"
APP_INSTALLATIONS_PATH = "/app/installations"


# ---------------------------------------------------------------------------
# errors — each carries the exit code the CLI must use
# ---------------------------------------------------------------------------


class AuditError(Exception):
    """Base class: an audit failure that must fail closed."""

    exit_code = EXIT_CONFIG


class ConfigError(AuditError):
    """Usage or configuration problem (no network was touched)."""

    exit_code = EXIT_CONFIG


class RegistryError(AuditError):
    """The registry could not be read or parsed — an instrument error."""

    exit_code = EXIT_REGISTRY


class ApiError(AuditError):
    """A GitHub API call failed, was unparseable, or paged incompletely."""

    exit_code = EXIT_API


class InvariantError(AuditError):
    """The tool's own arithmetic did not close."""

    exit_code = EXIT_INVARIANT


# ---------------------------------------------------------------------------
# secret handling
# ---------------------------------------------------------------------------


class Redactor:
    """Removes credential material from anything the tool prints.

    Defence in depth: the tool never puts a credential into a message in the
    first place, and this is the second line that keeps a third-party
    exception message (a URL, a header dump) from carrying one out.
    """

    def __init__(self) -> None:
        self._secrets: list[str] = []

    def add(self, value: str | None) -> None:
        if value and len(value) >= 8:
            self._secrets.append(value)

    def __call__(self, text: str) -> str:
        if not text:
            return text
        for secret in self._secrets:
            text = text.replace(secret, "<redacted>")
        return text


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HttpResponse:
    """One HTTP response, reduced to what this tool needs."""

    status: int
    headers: Mapping[str, str]
    body: bytes


Fetch = Callable[[str, str, Mapping[str, str], int], HttpResponse]


def _http_fetch(method: str, url: str, headers: Mapping[str, str], timeout: int) -> HttpResponse:
    """Real transport. The only place this tool touches the network."""
    request = urllib.request.Request(url, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(int(response.status), dict(response.headers), response.read())
    except urllib.error.HTTPError as error:
        # An HTTP error is a RESPONSE, not an exception: 404 is a meaningful
        # answer for a repo probe, so it must not be raised as a transport
        # failure. The body is read because GitHub puts a JSON error object
        # there; it is never printed.
        try:
            body = error.read()
        except Exception:  # pragma: no cover - defensive
            body = b""
        return HttpResponse(int(error.code), dict(error.headers or {}), body)
    except urllib.error.URLError as error:
        raise ApiError(f"cannot reach {url}: {error.reason}") from error
    except OSError as error:
        raise ApiError(f"cannot reach {url}: {error}") from error


class GitHubClient:
    """A thin, paginating, fail-closed GitHub REST client.

    The transport is injectable so the production code path can be exercised
    without a network. Nothing here swallows an error: every non-2xx that is
    not an expected probe answer raises, and an incomplete page walk raises.
    """

    def __init__(
        self,
        token: str,
        *,
        fetch: Fetch | None = None,
        timeout: int = 30,
        base_url: str = GITHUB_API,
    ) -> None:
        self._token = token
        self._fetch = fetch or _http_fetch
        self._timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.endpoints: list[str] = []

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }

    def request(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> tuple[int, Any, Mapping[str, str]]:
        """GET one resource. Returns (status, parsed_body_or_None, headers).

        A 4xx/5xx is returned, not raised — a repo probe needs to SEE a 404.
        An unparseable body on any status is an ApiError: a body this tool
        cannot read is a body it cannot reason about.
        """
        query = dict(params or {})
        url = self.base_url + path
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        response = self._fetch("GET", url, self._headers(), self._timeout)
        self.endpoints.append(f"GET {path}")
        payload: Any = None
        if response.body:
            try:
                payload = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ApiError(
                    f"GET {path} returned a body that is not JSON: {error}"
                ) from error
        return int(response.status), payload, dict(response.headers or {})

    def get_paginated(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        collection: str | None = None,
    ) -> list[Any]:
        """Collect EVERY page of a list endpoint, or fail closed.

        Completeness is proven two ways: the endpoint's ``total_count`` (the
        list endpoints this tool uses all carry one) must equal the number of
        items collected, and the ``Link`` header's ``rel="next"`` must be
        followed to the end. A walk that ends with a full page, no next link
        and no total_count is NOT provably complete, so it raises.
        """
        items: list[Any] = []
        seen: set[str] = set()
        page = 1
        total: int | None = None

        while True:
            query = dict(params or {})
            query["per_page"] = PER_PAGE
            query["page"] = page
            status, payload, headers = self.request(path, query)
            if status >= 400:
                raise ApiError(f"GET {path} failed with HTTP {status}")
            page_items, page_total = _extract_collection(payload, collection, path)
            if page_total is not None:
                if total is None:
                    total = page_total
                elif total != page_total:
                    raise ApiError(
                        f"GET {path}: total_count changed mid-walk "
                        f"({total} -> {page_total}); the listing is not stable"
                    )
            for item in page_items:
                key = _item_key(item)
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
            if _next_link(headers):
                page += 1
                continue
            if total is None and len(page_items) == PER_PAGE:
                raise ApiError(
                    f"GET {path}: a full page came back with no next-page link and "
                    f"no total_count - pagination cannot be proven complete"
                )
            break

        if total is not None and len(items) != total:
            raise ApiError(
                f"GET {path}: pagination incomplete - collected {len(items)} of "
                f"{total} items"
            )
        return items


def _extract_collection(
    payload: Any, collection: str | None, path: str
) -> tuple[list[Any], int | None]:
    """Pull the item list (and total_count, when the endpoint carries one)."""
    if collection is None:
        if not isinstance(payload, list):
            raise ApiError(f"GET {path}: expected a JSON array response")
        return payload, None
    if not isinstance(payload, dict) or collection not in payload:
        raise ApiError(f"GET {path}: expected a JSON object with a {collection!r} array")
    items = payload[collection]
    if not isinstance(items, list):
        raise ApiError(f"GET {path}: expected {collection!r} to be an array")
    total = payload.get("total_count")
    if not isinstance(total, int) or isinstance(total, bool):
        total = None
    return items, total


def _next_link(headers: Mapping[str, str]) -> str | None:
    """The ``rel="next"`` URL from a Link header, if there is one."""
    link = ""
    for key, value in (headers or {}).items():
        if str(key).lower() == "link":
            link = value or ""
            break
    for part in link.split(","):
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return None


def _item_key(item: Any) -> str:
    """A stable identity for a list item, so a repeated page cannot double-count."""
    if isinstance(item, Mapping):
        for field in ("full_name", "name", "id"):
            if field in item:
                return f"{field}:{item[field]}"
        return "json:" + json.dumps(item, sort_keys=True, default=str)
    return "raw:" + repr(item)


# ---------------------------------------------------------------------------
# the registry -> the universe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Universe:
    """The repos the App installation is audited against."""

    org: str
    forks: tuple[str, ...]
    first_party: tuple[str, ...]
    excluded: Mapping[str, str]
    duplicated: tuple[str, ...] = ()

    @property
    def members(self) -> tuple[str, ...]:
        """The DISTINCT repos in scope.

        A repo may be declared in both ``forks`` and ``_first_party`` — the
        registry does exactly that for one repo, whose ``forks`` entry carries
        the sentinel upstream ``"_first_party"``. Counting it twice would make
        the bucket arithmetic lie about how many repos exist, so the universe
        is the distinct set and the duplication is reported separately.
        """
        return tuple(sorted(set(self.forks) | set(self.first_party)))

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def entry_count(self) -> int:
        """How many registry ENTRIES the two sections hold (before de-dup)."""
        return len(self.forks) + len(self.first_party)


def load_registry(path: Path) -> dict[str, Any]:
    """Read the fork registry. An unreadable registry is an INSTRUMENT error."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise RegistryError(f"cannot read the fork registry {path}: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RegistryError(f"the fork registry {path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise RegistryError(f"the fork registry {path} is not a JSON object")
    return data


def _record_names(value: Any, label: str) -> tuple[str, ...]:
    """Repo names out of a registry section that may be a map or a list."""
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return tuple(sorted(str(key) for key in value.keys()))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        names: list[str] = []
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, Mapping):
                name = item.get("name") or item.get("repo") or item.get("full_name")
                if not isinstance(name, str) or not name.strip():
                    raise RegistryError(f"registry {label} entry has no usable name: {item!r}")
                names.append(name)
            else:
                raise RegistryError(f"registry {label} entry is not a name: {item!r}")
        return tuple(sorted(names))
    raise RegistryError(f"registry {label} is neither a map nor a list")


def _excluded_map(value: Any) -> dict[str, str]:
    """The ``_excluded`` section: repo name -> the reason it is not in scope."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(key): str(reason) for key, reason in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        excluded: dict[str, str] = {}
        for item in value:
            if isinstance(item, str):
                excluded[item] = ""
            elif isinstance(item, Mapping):
                name = item.get("name") or item.get("repo")
                if not isinstance(name, str) or not name.strip():
                    raise RegistryError(f"registry _excluded entry has no usable name: {item!r}")
                excluded[name] = str(item.get("reason", ""))
            else:
                raise RegistryError(f"registry _excluded entry is not a name: {item!r}")
        return excluded
    raise RegistryError("registry _excluded is neither a map nor a list")


def derive_universe(registry: Mapping[str, Any]) -> Universe:
    """Derive the repo universe from the registry.

    The universe is the DISTINCT set of ``forks`` + ``_first_party``. A repo
    declared in both sections is counted once and reported as a duplication —
    the registry does this for a repo whose ``forks`` entry carries the
    sentinel upstream ``"_first_party"``. ``_excluded`` is reported
    separately, with its reason, and is NOT in the universe.

    A repo that is both in scope and explicitly excluded is a contradiction
    the tool refuses to resolve on its own: that is a registry error, not a
    silent union.
    """
    org = registry.get("org")
    if not isinstance(org, str) or not org.strip():
        raise RegistryError("the fork registry has no 'org' string")
    forks = _record_names(registry.get("forks"), "forks")
    first_party = _record_names(registry.get("_first_party"), "_first_party")
    excluded = _excluded_map(registry.get("_excluded"))

    contradiction = sorted(set(excluded) & (set(forks) | set(first_party)))
    if contradiction:
        raise RegistryError(
            f"repos declared both in the universe and as excluded: {contradiction}"
        )
    duplicated = tuple(sorted(set(forks) & set(first_party)))
    return Universe(
        org=org.strip(),
        forks=forks,
        first_party=first_party,
        excluded=excluded,
        duplicated=duplicated,
    )


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepoStatus:
    """One repo's verdict."""

    name: str
    status: str
    reason: str


def classify(
    universe: Universe,
    covered: Iterable[str],
    resolved: Iterable[str],
    reasons: Mapping[str, str] | None = None,
) -> list[RepoStatus]:
    """Put every universe member in exactly one bucket.

    ``covered``  names the installation covers (case-folded).
    ``resolved`` names that were positively confirmed to exist in the org.
    ``reasons``  optional per-repo explanation for the unknown bucket.

    A repo that is neither covered nor resolved is UNKNOWN: no claim is made
    either way. That is the difference between a finding and an absence of
    knowledge, and the report keeps them apart.
    """
    covered_keys = {name.casefold() for name in covered}
    resolved_keys = {name.casefold() for name in resolved}
    reasons = reasons or {}
    statuses: list[RepoStatus] = []
    for name in universe.members:
        key = name.casefold()
        if key in covered_keys:
            statuses.append(
                RepoStatus(name, BUCKET_INSTALLED, "covered by the App installation")
            )
        elif key in resolved_keys:
            statuses.append(
                RepoStatus(
                    name,
                    BUCKET_NOT_INSTALLED,
                    "resolves in the org but is not covered by the App installation",
                )
            )
        else:
            statuses.append(
                RepoStatus(
                    name,
                    BUCKET_UNKNOWN,
                    reasons.get(
                        name, "repo name did not resolve; no claim is made either way"
                    ),
                )
            )
    return statuses


def build_report(
    *,
    mode: str,
    universe: Universe,
    statuses: Sequence[RepoStatus],
    installation: Mapping[str, Any],
    endpoints: Sequence[str],
    generated_at: str,
) -> dict[str, Any]:
    """Assemble the machine-readable report, asserting the arithmetic closes."""
    buckets: dict[str, list[str]] = {bucket: [] for bucket in BUCKETS}
    reasons: dict[str, str] = {}
    for status in statuses:
        buckets.setdefault(status.status, []).append(status.name)
        reasons[status.name] = status.reason
    counts = {bucket: len(buckets.get(bucket, [])) for bucket in BUCKETS}
    total = sum(counts.values())

    if total != universe.size:
        raise InvariantError(
            f"bucket arithmetic does not close: {counts} sums to {total}, "
            f"the universe is {universe.size}"
        )
    named = [status.name for status in statuses]
    if len(set(named)) != len(named) or set(named) != set(universe.members):
        raise InvariantError(
            "the classification does not cover every universe member exactly once"
        )

    not_installed = sorted(buckets.get(BUCKET_NOT_INSTALLED, []))
    unknown = sorted(buckets.get(BUCKET_UNKNOWN, []))
    complete = not unknown

    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "mode": mode,
        "complete": complete,
        "org": universe.org,
        "universe": {
            "size": universe.size,
            "entries": universe.entry_count,
            "forks": len(universe.forks),
            "first_party": len(universe.first_party),
            "excluded": len(universe.excluded),
            "declared_in_both_sections": list(universe.duplicated),
            "members": list(universe.members),
        },
        "installation": dict(installation),
        "endpoints": list(endpoints),
        "buckets": counts,
        "repos": {
            BUCKET_INSTALLED: sorted(buckets.get(BUCKET_INSTALLED, [])),
            BUCKET_NOT_INSTALLED: not_installed,
            BUCKET_UNKNOWN: [
                {"name": name, "reason": reasons.get(name, "")} for name in unknown
            ],
        },
        "not_installed": not_installed,
    }


def plan_report(universe: Universe, generated_at: str) -> dict[str, Any]:
    """The credential-free plan: what WOULD be audited, and what is excluded."""
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "mode": "plan",
        "complete": True,
        "org": universe.org,
        "universe": {
            "size": universe.size,
            "entries": universe.entry_count,
            "forks": len(universe.forks),
            "first_party": len(universe.first_party),
            "excluded": len(universe.excluded),
            "declared_in_both_sections": list(universe.duplicated),
            "members": list(universe.members),
        },
        "excluded": [
            {"name": name, "reason": reason}
            for name, reason in sorted(universe.excluded.items())
        ],
        "endpoints": [],
    }


# ---------------------------------------------------------------------------
# the audit itself
# ---------------------------------------------------------------------------


def _repo_name(item: Any) -> str:
    """The repo name from a GitHub repo object."""
    if not isinstance(item, Mapping):
        raise ApiError(f"expected a repository object, got {item!r}")
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        full_name = item.get("full_name")
        if isinstance(full_name, str) and "/" in full_name:
            name = full_name.rsplit("/", 1)[1]
        else:
            raise ApiError(f"repository object has no usable name: {item!r}")
    return name


def _probe_repo(client: GitHubClient, org: str, name: str) -> tuple[bool, str]:
    """Resolve one repo name. True = it exists; False = it did not resolve.

    Only 200 and 404 are answers. Any other status is an API failure and
    fails the whole audit closed: a 403 we cannot read is not evidence of
    absence.
    """
    path = f"/repos/{org}/{name}"
    status, _payload, _headers = client.request(path)
    if status == 200:
        return True, "resolved"
    if status == 404:
        return False, "the repo name did not resolve (HTTP 404)"
    raise ApiError(f"GET {path} failed with HTTP {status}")


def audit_installation(
    *,
    mode: str,
    universe: Universe,
    client: GitHubClient,
    coverage_path: str,
    installation: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Audit one installation's coverage of the universe.

    The credential itself is NOT a parameter: it lives in the client's
    Authorization header and has no business being anywhere near the report.
    The caller keeps it, and the caller registers it with the redactor.
    """
    covered_items = client.get_paginated(coverage_path, collection="repositories")
    covered = {_repo_name(item).casefold() for item in covered_items}

    resolved: set[str] = set()
    unresolved_reasons: dict[str, str] = {}
    for name in universe.members:
        if name.casefold() in covered:
            continue
        ok, reason = _probe_repo(client, universe.org, name)
        if ok:
            resolved.add(name.casefold())
        else:
            unresolved_reasons[name] = reason

    statuses = classify(universe, covered, resolved, unresolved_reasons)

    report = build_report(
        mode=mode,
        universe=universe,
        statuses=statuses,
        installation=installation,
        endpoints=client.endpoints,
        generated_at=generated_at,
    )
    return report


def _select_installation(
    client: GitHubClient, universe: Universe, wanted_id: str | None
) -> Mapping[str, Any]:
    """Pick the installation to audit: by id if asked, else the org's."""
    installations = client.get_paginated(
        APP_INSTALLATIONS_PATH, collection="installations"
    )
    if wanted_id:
        for installation in installations:
            if str(installation.get("id")) == str(wanted_id):
                return installation
        raise ApiError(f"the App has no installation with id {wanted_id}")
    matches = [
        installation
        for installation in installations
        if _account_login(installation) == universe.org.casefold()
    ]
    if not matches:
        raise ApiError(f"the App has no installation on {universe.org}")
    if len(matches) > 1:
        raise ApiError(
            f"the App has {len(matches)} installations on {universe.org}; "
            f"set GH_APP_INSTALLATION_ID to pick one"
        )
    return matches[0]


def _account_login(installation: Mapping[str, Any]) -> str:
    account = installation.get("account")
    if isinstance(account, Mapping):
        login = account.get("login")
        if isinstance(login, str):
            return login.casefold()
    return ""


def _installation_metadata(
    installation: Mapping[str, Any] | None, *, source: str, universe_org: str
) -> dict[str, Any]:
    if not installation:
        return {
            "id": None,
            "account": universe_org,
            "target_type": None,
            "repository_selection": None,
            "source": source,
            "note": "an installation token does not expose its installation id",
        }
    return {
        "id": str(installation.get("id")) if installation.get("id") is not None else None,
        "account": (installation.get("account") or {}).get("login"),
        "target_type": installation.get("target_type"),
        "repository_selection": installation.get("repository_selection"),
        "source": source,
    }


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------


def _read_token(args: argparse.Namespace, redactor: Redactor) -> str:
    """The installation token, from a file or the environment. Never printed."""
    if args.token_file:
        try:
            token = Path(args.token_file).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ConfigError(
                f"cannot read the token file {args.token_file}: {error}"
            ) from error
        if not token:
            raise ConfigError(f"the token file {args.token_file} is empty")
        redactor.add(token)
        return token
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "no installation token: pass --token-file <path> or set GH_TOKEN"
        )
    redactor.add(token)
    return token


def _load_build_app_jwt() -> Callable[..., str]:
    """Import the house JWT minter.

    ``gh_app_token`` guards its ``import jwt`` and exits 2 when PyJWT is
    absent, so the import is done lazily and the SystemExit is converted into
    a clean, fail-closed configuration error.
    """
    module_name = "pmoves_gh_app_token"
    module = sys.modules.get(module_name)
    if module is None:
        path = Path(__file__).resolve().parent / "gh_app_token.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ConfigError(f"cannot load the house JWT minter at {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except SystemExit as error:
            sys.modules.pop(module_name, None)
            raise ConfigError(
                "the house JWT minter (gh_app_token) refused to load - PyJWT is "
                "not available to this interpreter"
            ) from error
        except Exception as error:
            sys.modules.pop(module_name, None)
            raise ConfigError(
                f"cannot import the house JWT minter (gh_app_token): {error}"
            ) from error
    build = getattr(module, "build_app_jwt", None)
    if build is None:
        raise ConfigError("gh_app_token.build_app_jwt is missing")
    return build


def _read_app_credentials() -> tuple[str, str]:
    """The App id and private key, from the environment."""
    app_id = (
        os.environ.get("GH_APP_CLIENT_ID", "").strip()
        or os.environ.get("GH_APP_ID", "").strip()
    )
    private_key = os.environ.get("GH_APP_SEC", "").strip()
    if not app_id:
        raise ConfigError(
            "no App id: set GH_APP_CLIENT_ID (preferred) or GH_APP_ID"
        )
    if not private_key:
        raise ConfigError("no App private key: set GH_APP_SEC")
    # The funnel stores PEM bodies with literal \n escapes in some tiers.
    if "\\n" in private_key and "\n" not in private_key:
        private_key = private_key.replace("\\n", "\n")
    return app_id, private_key


def _mint_app_jwt(app_id: str, private_key: str) -> str:
    build = _load_build_app_jwt()
    try:
        return build(app_id, private_key)
    except Exception as error:
        raise ConfigError(f"could not mint an App JWT: {error}") from error


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(payload: Mapping[str, Any], path: Path | None) -> None:
    if path is None:
        return
    try:
        target = Path(path)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except OSError as error:
        raise ConfigError(f"cannot write the report to {path}: {error}") from error


def render_summary(report: Mapping[str, Any]) -> str:
    """The human summary. A failed audit never reaches this function."""
    universe = report.get("universe", {})
    lines: list[str] = []
    if report.get("mode") == "plan":
        lines.append("GitHub App installation audit - PLAN (no network, no credentials)")
        lines.append(f"  org: {report.get('org')}")
        lines.append(
            f"  universe: {universe.get('size')} distinct repos "
            f"({universe.get('entries')} registry entries = "
            f"{universe.get('forks')} forks + {universe.get('first_party')} first-party)"
        )
        duplicated = universe.get("declared_in_both_sections") or []
        if duplicated:
            lines.append(
                f"  declared in BOTH sections (counted once): {', '.join(duplicated)}"
            )
        excluded = report.get("excluded") or []
        lines.append(f"  explicitly excluded: {len(excluded)}")
        for entry in excluded:
            lines.append(f"    - {entry.get('name')}: {entry.get('reason')}")
        return "\n".join(lines)

    installation = report.get("installation", {})
    lines.append("GitHub App installation audit")
    lines.append(f"  mode: {report.get('mode')}")
    lines.append(f"  org: {report.get('org')}")
    lines.append(
        f"  installation: id={installation.get('id')} "
        f"account={installation.get('account')} "
        f"target={installation.get('target_type')}"
    )
    lines.append(
        f"  universe: {universe.get('size')} distinct repos "
        f"({universe.get('entries')} registry entries = "
        f"{universe.get('forks')} forks + {universe.get('first_party')} first-party), "
        f"{universe.get('excluded')} explicitly excluded"
    )
    duplicated = universe.get("declared_in_both_sections") or []
    if duplicated:
        lines.append(
            f"  declared in BOTH sections (counted once): {', '.join(duplicated)}"
        )
    endpoints = report.get("endpoints") or []
    lines.append(f"  endpoints used: {len(endpoints)}")
    for endpoint in endpoints:
        lines.append(f"    - {endpoint}")
    buckets = report.get("buckets", {})
    lines.append(f"  installed:     {buckets.get(BUCKET_INSTALLED, 0)}")
    lines.append(f"  not_installed: {buckets.get(BUCKET_NOT_INSTALLED, 0)}")
    lines.append(f"  unknown:       {buckets.get(BUCKET_UNKNOWN, 0)}")
    lines.append(f"  complete: {str(report.get('complete')).lower()}")

    not_installed = report.get("not_installed") or []
    lines.append(f"  NOT COVERED BY THE APP INSTALLATION ({len(not_installed)}):")
    if not_installed:
        for name in not_installed:
            lines.append(f"    - {name}")
    else:
        lines.append("    (none)")

    unknown = report.get("repos", {}).get(BUCKET_UNKNOWN) or []
    lines.append(f"  UNKNOWN - no claim made ({len(unknown)}):")
    if unknown:
        for entry in unknown:
            lines.append(f"    - {entry.get('name')}: {entry.get('reason')}")
    else:
        lines.append("    (none)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--plan",
        action="store_true",
        help="derive the repo universe from the registry; no network, no credentials",
    )
    mode.add_argument(
        "--token",
        action="store_true",
        help="audit with an installation token (GH_TOKEN or --token-file)",
    )
    mode.add_argument(
        "--app-jwt",
        action="store_true",
        help="audit with an App JWT minted by the house minter (gh_app_token)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the JSON report on stdout"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write the JSON report to this path"
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"the fork registry (default {DEFAULT_REGISTRY})",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=None,
        help="read the installation token from this file (never printed)",
    )
    parser.add_argument(
        "--installation-id",
        default=None,
        help="audit this installation id (default: GH_APP_INSTALLATION_ID, else the org's)",
    )
    parser.add_argument(
        "--fail-on-not-installed",
        action="store_true",
        help="exit non-zero when the installation does not cover every universe repo",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="per-request timeout in seconds"
    )
    return parser.parse_args(argv)


def _run(
    args: argparse.Namespace, *, fetch: Fetch | None, redactor: Redactor
) -> dict[str, Any]:
    registry = load_registry(args.registry)
    universe = derive_universe(registry)
    generated_at = _now_iso()

    if args.plan:
        return plan_report(universe, generated_at)

    if args.token:
        token = _read_token(args, redactor)
        client = GitHubClient(token, fetch=fetch, timeout=args.timeout)
        wanted_id = (
            args.installation_id
            or os.environ.get("GH_APP_INSTALLATION_ID", "").strip()
            or None
        )
        installation = _installation_metadata(
            {"id": wanted_id, "account": {"login": universe.org}}
            if wanted_id
            else None,
            source="installation-token",
            universe_org=universe.org,
        )
        return audit_installation(
            mode="token",
            universe=universe,
            client=client,
            coverage_path=INSTALLATION_REPOSITORIES_PATH,
            installation=installation,
            generated_at=generated_at,
        )

    # --app-jwt
    app_id, private_key = _read_app_credentials()
    app_jwt = _mint_app_jwt(app_id, private_key)
    redactor.add(app_jwt)
    client = GitHubClient(app_jwt, fetch=fetch, timeout=args.timeout)
    wanted_id = (
        args.installation_id
        or os.environ.get("GH_APP_INSTALLATION_ID", "").strip()
        or None
    )
    installation = _select_installation(client, universe, wanted_id)
    installation_id = installation.get("id")
    if installation_id is None:
        raise ApiError("the selected installation has no id")
    detail_status, detail, _headers = client.request(
        f"{APP_INSTALLATIONS_PATH}/{installation_id}"
    )
    if detail_status >= 400:
        raise ApiError(
            f"GET {APP_INSTALLATIONS_PATH}/{installation_id} failed with HTTP {detail_status}"
        )
    if isinstance(detail, Mapping):
        installation = detail
    return audit_installation(
        mode="app-jwt",
        universe=universe,
        client=client,
        coverage_path=f"{APP_INSTALLATIONS_PATH}/{installation_id}/repositories",
        installation=_installation_metadata(
            installation, source="app-jwt", universe_org=universe.org
        ),
        generated_at=generated_at,
    )


def main(argv: Sequence[str] | None = None, *, fetch: Fetch | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = _parse_args(argv)
    redactor = Redactor()
    try:
        report = _run(args, fetch=fetch, redactor=redactor)
        _write_json(report, args.out)
    except AuditError as error:
        message = redactor(str(error))
        failure = {
            "schema": SCHEMA,
            "generated_at": _now_iso(),
            "mode": getattr(args, "mode", None) or _mode_name(args),
            "complete": False,
            "failed": True,
            "error": message,
        }
        try:
            _write_json(failure, args.out)
        except AuditError:
            pass
        print(f"AUDIT FAILED (exit {error.exit_code}): {message}", file=sys.stderr)
        print(
            "AUDIT FAILED: no coverage verdict was produced. "
            "This is NOT 'zero repos missing'.",
            file=sys.stderr,
        )
        return error.exit_code

    summary = render_summary(report)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(summary, file=sys.stderr)
    else:
        print(summary)

    if not report.get("complete", False):
        unknown = len(report.get("repos", {}).get(BUCKET_UNKNOWN, []))
        print(
            f"AUDIT INCOMPLETE: {unknown} repo(s) could not be resolved. "
            f"The coverage verdict is NOT complete.",
            file=sys.stderr,
        )
        return EXIT_INCOMPLETE
    if args.fail_on_not_installed and report.get("not_installed"):
        print(
            f"AUDIT FAILED: {len(report['not_installed'])} repo(s) are not covered "
            f"by the App installation.",
            file=sys.stderr,
        )
        return EXIT_NOT_INSTALLED
    return EXIT_OK


def _mode_name(args: argparse.Namespace) -> str:
    if getattr(args, "plan", False):
        return "plan"
    if getattr(args, "token", False):
        return "token"
    if getattr(args, "app_jwt", False):
        return "app-jwt"
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
