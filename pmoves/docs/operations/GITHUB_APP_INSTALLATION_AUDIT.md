# GitHub App Installation Audit

**What it answers:** of the repos in the PMOVES.AI registry universe, which
ones does the GitHub App installation actually cover?

**Why it is a CI tool:** the App credentials (`GH_APP_ID`,
`GH_APP_CLIENT_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_SEC`) exist only in
GitHub Actions secrets. They are not on the operator's host, so the coverage
state cannot be measured there — the probes come back 401/404 from a host
that does not hold the credential. This tool runs where the credential lives.

- Instrument: `pmoves/tools/gh_app_installation_audit.py`
- Tests: `pmoves/tests/tools/test_gh_app_installation_audit.py`
- Mutation harness: `pmoves/tests/tools/test_gh_app_installation_audit_mutation_kill.py`
- CI: `.github/workflows/gh-app-installation-audit.yml`

---

## 1. The three modes

| Mode | Network | Credential | What it does |
|------|---------|------------|--------------|
| `--plan` | none | none | Derives the repo universe from `pmoves/config/fork_registry.json` and prints it. |
| `--token` | yes | an installation token (`GH_TOKEN` or `--token-file`) | Reads `GET /installation/repositories` and compares it to the universe. |
| `--app-jwt` | yes | `GH_APP_CLIENT_ID` / `GH_APP_ID` + `GH_APP_SEC` | Mints an App JWT with the house minter, lists the App's installations, selects one, and reads that installation's repository list. |

### `--plan` — proving the universe, on the operator's host

No network, no credentials. This is how the universe size gets *proven*
rather than asserted:

```powershell
python pmoves/tools/gh_app_installation_audit.py --plan
python pmoves/tools/gh_app_installation_audit.py --plan --json
```

The output on the current registry (tool output, not prose):

```
GitHub App installation audit - PLAN (no network, no credentials)
  org: POWERFULMOVES
  universe: 94 distinct repos (95 registry entries = 86 forks + 9 first-party)
  declared in BOTH sections (counted once): pmoves-hirag-mcp
  explicitly excluded: 1
    - Pmoves-cipher: No common ancestor with upstream — cannot sync via merge API
```

Two numbers, and they are not the same number:

- **registry entries** — every row under `forks` plus every row under
  `_first_party`.
- **distinct repos** — the universe the audit actually classifies. One repo
  (`pmoves-hirag-mcp`) is declared in *both* sections: its `forks` entry
  carries the sentinel upstream `"_first_party"`. It is counted once, and the
  duplication is reported rather than hidden.

The bucket counts sum to the **distinct repo** count, because that is the
number of repos that get classified.

`_excluded` entries are out of scope, and the plan prints each one **with
its reason**. A repo that is out of scope and silent is indistinguishable
from a repo nobody remembered.

> The `fork-sync.yml` workflow's sync scope is a **subset** of the universe
> (the repos it auto-syncs). It is not the universe, and the universe is not
> derived from it.

### `--token` — audit with an installation token in hand

```powershell
$env:GH_TOKEN = "<installation token>"
python pmoves/tools/gh_app_installation_audit.py --token --json --out report.json
```

or, from a file:

```powershell
python pmoves/tools/gh_app_installation_audit.py --token --token-file .pmoves/gh_app_token --json
```

The token is **never printed, logged, or written to the report** — not even
in a masked-but-partial form. Only metadata (credential kind, installation
id, account, endpoints) is emitted.

### `--app-jwt` — audit a specific installation, with no installation token

```powershell
$env:GH_APP_CLIENT_ID = "<client id>"
$env:GH_APP_SEC = "<PEM private key>"
$env:GH_APP_INSTALLATION_ID = "<installation id>"   # optional
python pmoves/tools/gh_app_installation_audit.py --app-jwt --json --out report.json
```

The JWT is minted by the house minter `pmoves/tools/gh_app_token.py`
(`build_app_jwt`, RS256 via PyJWT — no hand-rolled signer). This tool imports
that function; it does not reimplement signing. With no
`GH_APP_INSTALLATION_ID`, the tool selects the installation whose
`account.login` matches the registry's `org`, and refuses to guess if there
is more than one.

---

## 2. What CI does

`.github/workflows/gh-app-installation-audit.yml`:

1. Mints a short-lived installation token through the house reusable
   workflow `.github/workflows/_app-token.yml` (`secrets: inherit`,
   `owner: POWERFULMOVES`). The token reaches the audit through the `GH_TOKEN`
   environment variable — never through a printed argument and never through
   `argv`.
2. Runs the audit in `--token` mode and writes the JSON report to a file.
3. Publishes the verdict to `$GITHUB_STEP_SUMMARY` and uploads the report as
   a workflow artifact.
4. **Fails** when the audit exits non-zero, **and** when the report's
   `complete` flag is false. A missing report fails closed too.

The workflow runs on pull requests that touch the tool, its tests, the
workflow itself, or `pmoves/config/fork_registry.json` (the universe source),
plus a weekly schedule and manual dispatch.

`repositories` is intentionally left empty in the mint. The audit has to be
able to *see* every repo in the org; a token scoped to a subset cannot tell
an uncovered repo apart from one that does not exist. The token is read-only,
minted per run, and auto-revoked when the job ends.

---

## 3. Reading the report

```jsonc
{
  "schema": "pmoves.gh_app_installation_audit.v1",
  "mode": "token",                    // plan | token | app-jwt
  "complete": true,                   // false whenever anything was indeterminate
  "org": "POWERFULMOVES",
  "universe": {
    "size": 0,                        // distinct repos in scope
    "entries": 0,                     // registry entries (forks + first_party)
    "forks": 0,
    "first_party": 0,
    "excluded": 0,
    "declared_in_both_sections": [],
    "members": []
  },
  "installation": {
    "id": null,                       // installation id that was audited
    "account": "POWERFULMOVES",
    "target_type": "Organization",
    "repository_selection": null,
    "source": "installation-token"    // or app-jwt
  },
  "endpoints": ["GET /installation/repositories", "..."],
  "buckets": { "installed": 0, "not_installed": 0, "unknown": 0 },
  "repos": {
    "installed": [],
    "not_installed": [],
    "unknown": [{ "name": "...", "reason": "..." }]
  },
  "not_installed": []                 // THE actionable list
}
```

The three bucket counts plus the total **must** equal `universe.size`. The
tool asserts that equality itself and exits non-zero if it does not hold.

### The three buckets

| Bucket | Meaning | Operational reading |
|--------|---------|---------------------|
| `installed` | the installation's repo list contains it | covered — no action |
| `not_installed` | the repo resolves in the org but the installation does not cover it | **actionable**: install/select the App on this repo |
| `unknown` | the repo name could not be resolved, so no claim is made either way | **needs a human**: the registry and the org disagree, or the credential cannot see the repo |

`not_installed` is the answer the operator asked for. `unknown` is the
absence of an answer, and the two are never merged.

### "not installed" — what it actually means

A repo in `not_installed` **exists in the org** (the audit resolved its name)
and the **App installation does not cover it**. Operationally:

- the App is installed on the org with "selected repositories" and this repo
  was not selected; or
- the App is installed on a different account than the registry's `org`; or
- the installation's repository selection was changed after the last audit.

The fix is to include the repo in the App installation's repository selection
and re-run the audit.

### "unknown" — and why it is not a finding

A repo in `unknown` could not be resolved to an existing repo: GitHub said
404, or the repo is not in the org under that name, or the name moved. The
audit makes **no claim** about it — it is not in `not_installed`, because
"we cannot see it" is not "the App does not cover it".

A non-empty `unknown` bucket makes `complete: false` and **fails the CI
job**. That is deliberate: an audit that could not resolve every repo has
not answered the question, and a partial answer must not read as a clean
bill of health. The usual causes are a stale registry entry (a repo that was
renamed or deleted) or a credential that cannot see the org's private repos.

---

## 4. Fail-closed rules

The operator's hard rule: *a failed audit must never print a reassuring
summary*. The tool therefore exits non-zero, and prints this on stderr, when:

- the registry cannot be read or parsed (exit 3);
- a GitHub API call fails, returns an unparseable body, or a pagination walk
  cannot be proven complete (exit 4);
- the bucket arithmetic does not close (exit 5);
- at least one repo could not be resolved (exit 6);
- `--fail-on-not-installed` is set and the installation does not cover every
  universe repo (exit 7).

On any of those, the report written to `--out` carries `complete: false` and
**no bucket counts**, so it cannot be read as "zero repos missing". The
failure line is explicit:

```
AUDIT FAILED: no coverage verdict was produced. This is NOT 'zero repos missing'.
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | audit completed, coverage fully determined |
| 2 | usage / configuration error (bad arguments, missing credential, the house JWT minter refused to load) |
| 3 | the registry could not be read or parsed |
| 4 | a GitHub API call failed, was unparseable, or paged incompletely |
| 5 | the bucket arithmetic did not close |
| 6 | the audit is incomplete: at least one repo could not be resolved |
| 7 | gaps found and `--fail-on-not-installed` was set |

---

## 5. Reproducing the verification

```powershell
# the universe, derived (no credentials, no network)
python pmoves/tools/gh_app_installation_audit.py --plan
python pmoves/tools/gh_app_installation_audit.py --plan --json

# the tool's own tests + the mutation harness (no network, no credentials)
python -m pytest pmoves/tests/tools/test_gh_app_installation_audit.py `
  pmoves/tests/tools/test_gh_app_installation_audit_mutation_kill.py -v

# the workflow is valid YAML
python -c "import yaml;yaml.safe_load(open('.github/workflows/gh-app-installation-audit.yml',encoding='utf-8'));print('workflow yaml ok')"
```

The mutation harness mutates `pmoves/tools/gh_app_installation_audit.py`,
asserts that a NAMED test goes red, and restores the file byte-exactly. If a
mutation survives, the harness fails — a green harness is a claim that can
be pointed at.

---

## 6. What could not be verified here

The live installation state **cannot** be verified from the operator's host,
and this tool does not pretend otherwise. Measured on the operator's Windows
host with an authenticated `gh` CLI (org admin):

- `gh api orgs/POWERFULMOVES/installations` → **404** (the CLI OAuth token
  lacks `user`/`read:org`);
- `gh api /app/installations` → **401**;
- `gh api repos/OWNER/REPO/installation` → **401**.

So the coverage verdict comes from CI, where the App credentials live. The
`--plan` mode is the part that is verifiable locally, and it is what proves
the universe the CI run will audit.
