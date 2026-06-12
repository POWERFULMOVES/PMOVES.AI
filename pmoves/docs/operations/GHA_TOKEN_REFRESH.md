# GHA Token Auto-Refresh

Keeps `env.shared`'s `GITHUB_PAT` from going **stale**, which is the root cause of
the runner-bootstrap poison saga: a one-shot snapshot of the gh keyring token
drifts over time, and `gh` *inside make recipes* prefers the stale `GH_TOKEN`/
`GITHUB_TOKEN` env value over the keyring — so runner registration, PAT refresh,
and `actions/runners` queries fail with "scopes ['gist'] insufficient" while the
keyring token was valid the whole time.

## The pieces

| Piece | What it does |
|---|---|
| `pmoves/tools/inject_github_pat_from_gh_cli.py` | Snapshots the **keyring** token into `env.shared`. Now **env-isolated** (strips ambient `GH_TOKEN`/`GITHUB_TOKEN` so it reads the keyring, never the poison) and **behaviorally validated** (hits `repos/<owner>/<repo>/actions/runners`, not `/user`). Adds `--refresh-if-stale` (idempotent) + `--quiet`. |
| `make -C pmoves gha-token-refresh` | Idempotent wrapper: runs `--refresh-if-stale`; on a refresh (exit 75) it runs `secrets-funnel-sync` to propagate into `env.tier-*`; on the common no-op tick it does nothing. Safe to run on a timer. |
| `deploy/provision/common/register-token-refresh.ps1` | Registers a Windows Task Scheduler job (Z890) running the make target every N hours **as the host user** (so it has the gh keyring). |
| `deploy/provision/common/register-token-refresh.sh` | Same for Linux nodes — systemd **user** timer (preferred) or crontab fallback. |

## Why host-side, not a GitHub Actions job

The gh keyring is a **host user-profile artifact**. The dockerized `ai-lab` runner
is isolated from it, and a cloud Actions runner has no access to the host's
`env.shared` at all. The App can mint only short-lived *installation* tokens, not
a durable PAT — so the refresh re-snapshots the **keyring** token on the host
where it lives. (If a node ever moves to App-installation-token-on-demand, the
recipes would mint per-invocation and this snapshot becomes unnecessary.)

## Behavioral validation > string-scope

`gh auth status` reports **no classic scopes** for a fine-grained PAT, so the old
string-scope gate (`admin:org` OR `repo`+`workflow`) **false-negatives** a token
that can actually do the job. The authoritative check is behavioral: can the
token reach `repos/<owner>/<repo>/actions/runners`? The token under test is passed
via an env-isolated `GH_TOKEN` so a poisoned ambient var can't mask a bad token.

## Activate (per node)

```powershell
# Z890 (Windows) — run as the host user, in a shell where `gh auth status` is green
pwsh -File deploy/provision/common/register-token-refresh.ps1            # every 6h
pwsh -File deploy/provision/common/register-token-refresh.ps1 -IntervalHours 4
```

```bash
# Linux nodes (5090 / Knuckles / KVMs)
deploy/provision/common/register-token-refresh.sh                        # every 6h
INTERVAL_HOURS=4 deploy/provision/common/register-token-refresh.sh
```

Run-now / one-shot check:

```bash
make -C pmoves gha-token-refresh                                # idempotent: refresh iff stale
python pmoves/tools/inject_github_pat_from_gh_cli.py --check    # "can this token do runner-ctl's job?"
```

Logs land in `.git/token-refresh.log` (gitignored). Exit codes: `0` current/no-op,
`75` refreshed (funnel-sync ran), `2` keyring token can't reach `actions/runners`
(re-auth: `gh auth refresh --scopes admin:org,repo,workflow`).

## Related
- `pmoves/mk/infra.mk` — `gha-runner-ctl-setup-pat` (one-shot) + `gha-token-refresh` (scheduled)
- Memory: `project_cross_compat_runner_token_poison` — the root-cause saga this prevents
