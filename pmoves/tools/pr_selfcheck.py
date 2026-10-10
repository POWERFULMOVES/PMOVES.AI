#!/usr/bin/env python3
"""Pre-PR self-verification against the four LEARNINGS buckets.

Self-verify -> learnings -> evo, operator-adopted 2026-10-03. The LEARNINGS
template (pmoves/docs/templates/PR_LEARNINGS.template.md) classifies REVIEW
threads after the fact; this tool runs the same taxonomy against a diff
BEFORE the PR opens, so the cheap catches (the ones reviewers kept finding)
die in the worktree instead of in a review thread.

Every check is a real catch from a real PMOVES review (cited in each
check's docstring). A check failure is a WARNING with the fix pattern, not
a block: the agent decides. The report ends with a verdict and writes a
structured sidecar (the evo feed) under docs/logs/selfcheck/.

Usage:
    python3 pmoves/tools/pr_selfcheck.py [--base origin/main] [--head HEAD]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]      # .../pmoves
GIT_ROOT = Path(__file__).resolve().parents[2]    # repo root (git -C target)

BUCKETS = ("missed-signal", "fix-pattern", "wrong-suggestion", "already-addressed")


@dataclass
class Finding:
    bucket: str
    check: str
    file: str
    detail: str
    fix_pattern: str


@dataclass
class Report:
    branch: str
    files: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.findings


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(GIT_ROOT), *args], capture_output=True, text=True, check=True
    ).stdout


def diff_names(base: str, head: str, deleted: bool = True) -> list[str]:
    filt = [] if deleted else ["--diff-filter=d"]
    return _git("diff", "--name-only", *filt, f"{base}...{head}").split()


def diff_for(base: str, head: str, path: str) -> str:
    return _git("diff", f"{base}...{head}", "--", path)


def blob(head: str, path: str) -> str | None:
    """File content at head; None when the path does not exist there (e.g.
    deleted in this branch). The first version raised and the whole check
    silently skipped (PR #3278 thread 4)."""
    r = subprocess.run(
        ["git", "-C", str(GIT_ROOT), "show", f"{head}:{path}"],
        capture_output=True,
        text=True,
    )
    return r.stdout if r.returncode == 0 else None


# --- checks: each cites the review that taught it ---------------------------


def check_format_braces_in_templates(report: Report, base: str, head: str) -> None:
    """Unescaped braces inside a .format() template. PR #3269 (nats bridge):
    the template's own comment carried '{ users }' and 'jetstream {' and
    rendering died with KeyError at the worst moment (first live use).
    Review-hardened (PR #3278 threads 1+2): the template body comes from the
    AST (exact literal, no quote-scanning), and a token is suspicious when
    its RAW inner text is not a strict .format() field - spaces inside the
    braces ('{ users }') are legal Python but never intended in a template,
    and the first version normalized them away, waving through exactly the
    shape it existed to catch."""
    for name in diff_names(base, head, deleted=False):
        if not name.endswith(".py"):
            continue
        text = blob(head, name)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(t, ast.Name)
                and re.fullmatch(r"[A-Z][A-Z_]*TEMPLATE[A-Z_]*", t.id)
                for t in node.targets
            ):
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            for line_no, line in enumerate(node.value.value.splitlines(), 1):
                for token in re.findall(r"\{[^{}\n]*\}", line):
                    inner = token[1:-1]
                    if re.fullmatch(r"[a-zA-Z_]\w*(!r|!s|:[^{}]*)?|", inner):
                        continue  # a strict field: name with optional conv/format spec
                    report.findings.append(
                        Finding(
                            "fix-pattern",
                            "format-braces-in-template",
                            name,
                            f"template literal line {line_no}: raw token {token} is not a strict "
                            ".format() field (spaces/punctuation inside braces are legal Python "
                            "but never intended in a template)",
                            "escape literal braces ({{ }}) everywhere in the template, comments included",
                        )
                    )
                    break


def check_phony_covers_new_targets(report: Report, base: str, head: str) -> None:
    """A new make target missing from .PHONY. PR #3269 thread 5: the most
    dangerous target in the lane (render-final) was the only one left off,
    so it alone could be shadowed by a stray same-named file."""
    mk = [n for n in diff_names(base, head) if n.endswith(("Makefile", ".mk"))]
    if not mk:
        return
    for name in mk:
        d = diff_for(base, head, name)
        added = [t for t in re.findall(r"^\+(\w[\w-]*):(?!=)", d, re.M)]
        if not added:
            continue
        text = blob(head, name)
        phony = " ".join(re.findall(r"^\.PHONY:\s*(.+)$", text, re.M)).split()
        for target in sorted(set(added) - set(phony)):
            report.findings.append(
                Finding(
                    "fix-pattern",
                    "phony-covers-new-targets",
                    name,
                    f"new target '{target}' is in no .PHONY line",
                    "add it to the nearest .PHONY; a same-named file could shadow the road",
                )
            )


def check_grep_pipeline_fails_closed(report: Report, base: str, head: str) -> None:
    """An INLINE command substitution feeding a docker verb. PR #3269 thread
    4: `docker kill --signal=SIGHUP $(grep ...)` with no match handed docker
    an empty argument and failed with an error naming neither NATS nor
    containers. Review-hardened (PR #3278 thread 3): fires ONLY on inline
    substitution (the verb and $$( on the same line with no assignment in
    between). A recipe that resolves into a variable first - whatever the
    variable is named, however it guards - is the fixed shape and is not
    flagged."""
    for name in diff_names(base, head, deleted=False):
        if not name.endswith(("Makefile", ".mk")):
            continue
        for line in diff_for(base, head, name).splitlines():
            if not line.startswith("+"):
                continue
            body = line[1:]
            # inline = docker verb followed by the substitution on this line,
            # with no '=' assignment ahead of it (assignment = resolved var)
            if re.search(r"docker\s+(kill|rm|stop|exec)\b[^\n]*\$\$\(", body) and not re.match(
                r"\s*[\w.-]+\s*=\s*\$\$", body.lstrip("@\t-")
            ):
                report.findings.append(
                    Finding(
                        "fix-pattern",
                        "grep-pipeline-fails-closed",
                        name,
                        f"docker verb fed by an INLINE $$() substitution: {body.strip()[:70]}",
                        "resolve into a variable first, then fail with a named error when it is empty",
                    )
                )


def check_ratchet_baselines_fresh(report: Report, base: str, head: str) -> None:
    """Fixing a baselined failure requires dropping its entry. #3250, #3251
    and #3244 all tripped stale-baseline CI: the ratchet runs on the PR ref
    and demands removed entries for failures the PR fixes. Reminder-class
    when the diff touches tests or the code they exercise."""
    names = diff_names(base, head)
    if any(
        n.startswith(("pmoves/tests/", "pmoves/scripts/")) for n in names
    ):
        report.findings.append(
            Finding(
                "missed-signal",
                "ratchet-baselines-fresh",
                "(reminder)",
                "diff touches tests/scripts: a baselined failure fixed here must have its entry dropped",
                "after CI's first run, drop every 'no longer fail' entry from "
                "_known_failures.yaml / _known_gaps.yaml",
            )
        )


def check_hand_edited_generated_files(report: Report, base: str, head: str) -> None:
    """Machine-emitted files edited by hand. PR #3269 thread 2: the v1
    secrets manifest is GENERATED from the v2 registry; a hand edit either
    gets overwritten or drifts. Same class: docker-compose.core.yml is
    split from docker-compose.yml."""
    GENERATED = {
        "pmoves/chit/secrets_manifest.yaml": (
            "edit the REGISTRY in tools/chit_manifest_register.py, then make chit-manifest-sync"
        ),
        "pmoves/docker-compose.core.yml": (
            "edit pmoves/docker-compose.yml, then scripts/split_compose.py"
        ),
    }
    for name in diff_names(base, head):
        if name in GENERATED:
            report.findings.append(
                Finding(
                    "fix-pattern",
                    "hand-edited-generated-file",
                    name,
                    "generated file edited directly in this diff",
                    GENERATED[name],
                )
            )


def check_line_number_citations(report: Report, base: str, head: str) -> None:
    """Line-number citations to mutable files. PR #3246 threads 3: comments
    citing '.gitignore:47' drifted twice from inserts inside the same PR.
    Cite patterns/keys, not line numbers."""
    for name in diff_names(base, head):
        d = diff_for(base, head, name)
        for line in d.splitlines():
            if line.startswith("+") and re.search(
                r"\.gitignore:\d+|\.yaml:\d+|\.conf:\d+", line
            ):
                report.findings.append(
                    Finding(
                        "fix-pattern",
                        "line-number-citation",
                        name,
                        f"added line cites a mutable file by line number: {line[1:70].strip()}",
                        "cite the pattern/key name instead; line numbers drift",
                    )
                )
                break


CHECKS = (
    check_format_braces_in_templates,
    check_phony_covers_new_targets,
    check_grep_pipeline_fails_closed,
    check_ratchet_baselines_fresh,
    check_hand_edited_generated_files,
    check_line_number_citations,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)

    branch = _git("rev-parse", "--abbrev-ref", "HEAD").strip()
    report = Report(branch=branch, files=diff_names(args.base, args.head))
    for check in CHECKS:
        try:
            check(report, args.base, args.head)
        except subprocess.CalledProcessError as exc:
            # a check that dies must be VISIBLE, not silent: the first version
            # swallowed this and one deleted .py file blanked a whole check
            # (PR #3278 thread 4)
            print(f"  [missed-signal] check-error: {check.__name__} skipped ({exc})", file=sys.stderr)

    print(f"selfcheck: {branch} vs {args.base} ({len(report.files)} files)")
    for f in report.findings:
        print(f"  [{f.bucket}] {f.check}: {f.file}")
        print(f"    {f.detail}")
        print(f"    fix: {f.fix_pattern}")
    verdict = "CLEAN" if report.passed else f"{len(report.findings)} finding(s)"
    print(f"verdict: {verdict}")

    sidecar_dir = PMOVES / "docs" / "logs" / "selfcheck"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", branch)
    sidecar = sidecar_dir / f"{safe}.json"
    sidecar.write_text(
        json.dumps(
            {
                "branch": branch,
                "base": args.base,
                "files": report.files,
                "findings": [asdict(f) for f in report.findings],
                "verdict": verdict,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"evo sidecar: {sidecar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
