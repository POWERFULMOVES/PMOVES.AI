# PMOVES Agent0 Plugin Pack

Local staging area for PMOVES plugin index submissions to:
- `https://github.com/agent0ai/a0-plugins`

This folder is not the upstream index. It is a deterministic prep lane for:
- `plugin.yaml` manifest drafting
- rule validation before opening external PRs
- atomic split of one-plugin-per-PR payloads

## Layout

- `catalog/<plugin-name>/plugin.yaml`:
  local draft manifests, one folder per plugin.

## Validation

- Local structural checks:
  - `make -C pmoves a0-plugins-check`
- Strict checks including remote GitHub repository + root `plugin.yaml`:
  - `make -C pmoves a0-plugins-check-remote`

Both commands mirror the upstream `a0-plugins` validator constraints:
- allowed keys: `title`, `description`, `github`, `tags`
- required keys: `title`, `description`, `github`
- title <= 50 chars, description <= 500 chars, tags <= 5
- one plugin folder per upstream PR
- no `_` prefix for plugin folder names

## Submission flow (targeted PRs)

1. Create/prepare plugin repository with root `plugin.yaml`.
2. Update matching `catalog/<name>/plugin.yaml` in this repo.
3. Run:
   - `make -C pmoves a0-plugins-check-remote`
4. Copy one plugin folder into `agent0ai/a0-plugins/plugins/<name>/`.
5. Open upstream PR with exactly one plugin folder.

## Candidate PMOVES plugin lanes

- `pmoves-mcp-mesh`
- `pmoves-chit-geometry-bus`
- `pmoves-discord-intake`
- `pmoves-swarm-attribution`

These are staged as initial manifests and should be pointed at final plugin
repositories before upstream submission.
