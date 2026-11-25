#!/usr/bin/env python3
'''Register-citation checker (zero-LLM deterministic audit).

Incident (PR #3408, merged 2026-10-24 with review threads unresolved): three
citations pointed at AGNOTE4482PHI.t1.md:3410 for claims the register does not
contain. The register is append-only: line numbers rot as rows land, so bare
line citations are unverifiable by construction.

Rules:
1. REJECT bare line citations: AGNOTE4482PHI.t1.md:<line>
2. Canonical tokens must resolve:
   AGNOTE4482[<owner>@<branch> @<YYYY-MM-DDTHH:MM:SSZ>]
   resolves iff some register row starts with <ts> and carries branch <branch>.

Usage: verify_register_citations.py [--register PATH] DOC...
Exit 0 clean; exit 1 lists violations.
'''
import argparse
import pathlib
import re
import sys

BARE = re.compile(r'AGNOTE4482PHI\.t1\.md:[0-9]+')
TOKEN = re.compile(r'AGNOTE4482\[([^@\]]+?)@([^@\]]+?)\s*@([0-9-]{10}T[0-9:]{8}Z)\]')


def row_matches(row, ts, branch):
    lead = row.lstrip('- `')
    if not lead.startswith(ts):
        return False
    return ('branch: `' + branch + '`' in row) or ('branch: ' + branch in row)


def main():
    ap = argparse.ArgumentParser(description='Verify AGNOTE4482 register citations in docs.')
    ap.add_argument('docs', nargs='+')
    ap.add_argument('--register', default='pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md')
    args = ap.parse_args()

    reg = pathlib.Path(args.register)
    rows = reg.read_text(errors='replace').splitlines() if reg.exists() else []

    violations = []
    for doc in args.docs:
        p = pathlib.Path(doc)
        for ln, line in enumerate(p.read_text(errors='replace').splitlines(), 1):
            for m in BARE.finditer(line):
                violations.append(f'{p}:{ln}: bare line citation {m.group(0)!r} — cite AGNOTE4482[owner@branch @ts] instead')
            for m in TOKEN.finditer(line):
                owner, branch, ts = m.groups()
                if not any(row_matches(r, ts, branch) for r in rows):
                    violations.append(f'{p}:{ln}: unresolvable token {m.group(0)!r}')

    if violations:
        print('REGISTER CITATION VIOLATIONS:')
        print('\n'.join(violations))
        return 1
    print('OK: no bare line citations; all AGNOTE4482[...] tokens resolve.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
