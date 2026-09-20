# Hardening tooling vs vendor documentation - the diff

**Status:** IN PROGRESS (scaffold committed first; sessions on this node cycle)
**Lane:** `docs/hardening-vendor-reconcile` - claimed by `B850-CLAUDE (Knuckles)`
**Date:** 2026-09-20

## What this document is

The **delta** between what PMOVES' hardening tooling, CI and docs actually do, and
what Docker's and GitHub's own documentation says. Not a restatement of what we
already do - a tool audited only against its own repo can only confirm its own
assumptions.

Three directions, because usually only the first gets checked:

1. Vendor recommends -> we do not implement or check.
2. We implement -> vendor has since changed, deprecated or contradicted. This is
   the direction that silently rots.
3. Our doc describes a protection -> our tooling does not enforce it.

Every finding is anchored to a vendor primary source by URL and section. Claims
that could not be anchored are marked **COULD-NOT-VERIFY** rather than asserted.

## Sections

- Findings ranked by severity - *pending*
- Vendor areas with NO corresponding PMOVES check - *pending*
- COULD-NOT-VERIFY - *pending*
