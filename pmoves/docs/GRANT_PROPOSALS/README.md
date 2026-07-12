# PMOVES.AI Grant Proposals

Canonical home for grant proposal materials for **PMOVES.AI**, the open-source multi-agent AI infrastructure operated by CATACLYSM STUDIOS, INC. (Russell Richardson, principal — Bronx, NY).

## Active proposals

| File | Status | Audience |
|------|--------|----------|
| [`PMOVES_AI_GRANT_PROPOSAL_2026.md`](./PMOVES_AI_GRANT_PROPOSAL_2026.md) | **v3.1 — current** (grounded 2026-07-11) | Grantor-agnostic public-benefit infrastructure proposal — tailor §1 / §3 / §5 per RFP |

This directory is the single tracked home for the 2026 proposal. (A richer working draft previously lived untracked under `CATACLYSM_STUDIOS_INC/`; its content has been promoted here and grounded, so treat this copy as authoritative.)

## Related materials (cross-reference when assembling a submission)

All links are absolute GitHub URLs so this index travels intact when extracted.

| Topic | Path |
|-------|------|
| Fordham Hill (Bronx) cooperative pilot proposal | [`Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/CATACLYSM_STUDIOS_INC/L2-DESIGN/proposals/Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md) |
| 5-year financial projections (illustrative — not audited) | [`PMOVES-5-Year-Financial-Model.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/CATACLYSM_STUDIOS_INC/PMOVES-5-Year-Financial-Model.md) |
| Cataclysm Studios platform vision & brand identity | [`CATACLYSM_STUDIOS_INC.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md) |
| Architecture thesis (cite for technical depth) | [`PMOVES_MOF_ARCHITECTURE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md), [`PMOVES_GRAND_CONVERGENCE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md) |
| Hardened deployment playbook (cite for security posture) | [`PMOVES.AI-Edition-Hardened-Full.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/docs/PMOVES.AI-Edition-Hardened-Full.md) |
| Rooms-on-a-stage model | [`ROOMS_ON_A_STAGE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/ROOMS_ON_A_STAGE.md), [`ROOM_MANIFEST_CONTRACT.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/ROOM_MANIFEST_CONTRACT.md) |

## When updating a proposal

1. **Refresh repository metrics** before submission — `git rev-list --count origin/main` (commits) and `gh pr list --state merged` (merged PRs). The repo squash-merges, so `git log --grep "Merge pull request"` undercounts.
2. **Verify every link** points to a tracked file on `main` (submodule gitlinks like `PMOVES-Tailscale` resolve on GitHub even though `git cat-file` can't).
3. **Plug in real budget numbers** — placeholder `$X` figures must be replaced with grounded estimates (hardware quotes, FTE) before submission.
4. **Tailor framing** to the specific grantor (see §10 of the proposal for the per-grantor decision points).
5. **Bump the version line** in the proposal header so prior reviewers can see what changed.

## Provenance

`v3.1` (2026-07-11) grounded the repository metrics (3,864 commits / 1,791 merged PRs), reconciled the untracked `CATACLYSM_STUDIOS_INC` draft into this canonical location, and added the rooms-on-a-stage, multi-engine voice fleet, and publishing-control-plane capabilities that landed after the v3.0 draft. Prior versions: `git log -- pmoves/docs/GRANT_PROPOSALS/PMOVES_AI_GRANT_PROPOSAL_2026.md`.
