Generate a situation report for the 5090 node — git state, runtime health, open work, and fleet context.

## Implementation

```bash
echo "=== 5090 SITREP ==="
echo "Time: $(date -Iseconds)"
echo ""

echo "--- Git ---"
git -C . log --oneline -5
echo "Branch: $(git -C . branch --show-current)"
echo "Dirty: $(git -C . status --porcelain | wc -l) files"
echo ""

echo "--- Services ---"
docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "pmoves|supabase|tensorzero" || echo "No matching PMOVES containers running"
echo ""

echo "--- GPU ---"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "GPU: nvidia-smi not available (no driver or no GPU)"
echo ""

echo "--- Ollama Models ---"
ollama list 2>/dev/null || echo "Ollama: not running or not installed"
echo ""

echo "--- Fleet ---"
tailscale status 2>/dev/null | grep -E "pmoves|z890|4090" || echo "Fleet: Tailscale not connected or no matching peers"
echo ""

echo "--- Open PRs ---"
gh pr list --state open --limit 5 2>/dev/null || echo "PRs: gh CLI not authenticated or not installed"
```

## Notes

- Use before AGNOTE4482 claim/release
- Share output during handoff between Claude/Codex/KiloCode
