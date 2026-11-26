"""Gate: every `docker compose` step in deploy-gateway-agent.yml satisfies every
`:?` guard that pmoves/docker-compose.yml declares.

WHY THIS GATE EXISTS
--------------------
`docker compose` interpolates the WHOLE compose file before it builds or
starts ANY service. So a required variable -- `${VAR:?message}` -- that
belongs to a service this workflow does not deploy still has to have a value,
or the compose parse fails before it does anything.

`deploy-gateway-agent.yml` therefore carries a hand-written list of
placeholder variables to satisfy those guards. That list is a MIRROR of the
compose file's guards, and mirrors drift.

MEASURED 2026-11-05: the mirror had drifted. Three guards --
`CHIT_PASSPHRASE` (wger-nats-bridge), `SECRET_KEY` (tokenism-simulator) and
`SUPABASE_JWT_SECRET` (a2ui-renderer) -- were absent from EVERY build,
deploy and rollback step, because the list carried the near-miss names
`CHIT_PROD_PASSPHRASE`, `SECRET_KEY_BASE` and `JWT_SECRET` instead. The
workflow therefore failed on every push to main since 2026-09-28 (15+
consecutive runs), while the workflow's own comment at the diagnostic step
already said "the compose file carries ${VAR:?} guards for OTHER services ...
that aren't set in this step's env, so a compose parse fails".

This gate recomputes the missing set from the compose file on every run, so
the mirror cannot drift again.

FAIL CLOSED
-----------
If the compose file cannot be read, or the workflow cannot be parsed, or no
`docker compose` step can be found, this test FAILS. A gate that cannot read
its input must not pass vacuously.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPO_ROOT / "pmoves" / "docker-compose.yml"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "deploy-gateway-agent.yml"

# `${VAR:?message}` -- the `:?` form is REQUIRED: compose refuses to
# interpolate when the variable is unset or empty.
REQUIRED_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):\?[^}]*\}")


def _compose_required_vars() -> set[str]:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    return {m.group(1) for m in REQUIRED_VAR_RE.finditer(text)}


def _runs_compose(run: str) -> bool:
    """True when a step really EXECUTES `docker compose`.

    Comment lines do not count. The workflow's diagnostic steps deliberately
    fall back to RAW docker, and say so in a comment that names
    `docker compose` -- so matching the bare text would demand the guards
    from a step that never runs compose, and the gate would be wrong about
    its own subject.
    """
    for line in run.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "docker compose" in stripped:
            return True
    return False


def _compose_steps() -> list[tuple[str, set[str]]]:
    """Every step that runs `docker compose`, with the env vars it sets."""
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_FILE.exists(), f"the deploy workflow must exist: {WORKFLOW_FILE}"
    workflow = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), "the workflow must parse into a mapping"

    found: list[tuple[str, set[str]]] = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        job = job or {}
        job_env = set((job.get("env") or {}))
        for step in (job.get("steps") or []):
            step = step or {}
            if not _runs_compose(str(step.get("run") or "")):
                continue
            env = step.get("env") or {}
            assert isinstance(env, dict), (
                f"step {step.get('name')!r} in job {job_name!r} has an env that "
                f"is not a mapping: {env!r}"
            )
            found.append((f"{job_name}/{step.get('name')}", job_env | set(env)))

    assert found, (
        "no step in deploy-gateway-agent.yml runs `docker compose`; the gate "
        "would pass vacuously, so it fails instead"
    )
    return found


def _missing_guards(
    required: set[str], steps: list[tuple[str, set[str]]]
) -> list[tuple[str, list[str]]]:
    return [
        (label, sorted(required - env_vars))
        for label, env_vars in steps
        if required - env_vars
    ]


def test_every_compose_step_satisfies_every_required_guard() -> None:
    """The gate that keeps the workflow's placeholder mirror honest."""
    required = _compose_required_vars()
    assert required, (
        f"no `:?` guards found in {COMPOSE_FILE}; the regex or the compose "
        f"file changed, and the gate would pass vacuously"
    )

    steps = _compose_steps()
    failures = _missing_guards(required, steps)

    assert not failures, (
        "these `docker compose` steps do not satisfy every `:?` guard that "
        "pmoves/docker-compose.yml declares, so `docker compose` will refuse "
        "to interpolate and the step will fail:\n"
        + "\n".join(
            f"  {label}: missing {', '.join(missing)}"
            for label, missing in failures
        )
    )


def test_the_gate_would_notice_a_missing_guard() -> None:
    """The gate has to be able to FAIL, or it is decoration.

    MEASURED 2026-11-05: this gate exists because the placeholder mirror in
    the workflow had drifted for a month -- three guards missing from every
    step -- and nothing noticed, because the workflow simply failed on every
    push and the failure was read as "the deploy is flaky".

    So the gate is run against the REAL steps with ONE guard removed from
    ONE step's env. If it does not report that guard, the gate is not doing
    its job, and this test fails.
    """
    required = _compose_required_vars()
    steps = _compose_steps()

    label, env_vars = steps[0]
    probe = sorted(required - env_vars) or [sorted(required)[0]]
    probe = probe[0]

    broken = list(steps)
    broken[0] = (label, set(env_vars) - {probe})

    failures = _missing_guards(required, broken)
    assert failures, (
        "removing a guard the compose file declares did NOT make the gate "
        "report it -- the gate cannot fail, so it is decoration"
    )
    reported_label, reported_missing = failures[0]
    assert reported_label == label
    assert probe in reported_missing, (
        f"the gate reported {reported_missing}, which does not include the "
        f"guard that was removed ({probe})"
    )
