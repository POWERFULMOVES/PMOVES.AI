# List Work Items

List available work items from the PMOVES-BoTZ work items registry.

## Arguments

- `$ARGUMENTS` - Optional: integration name filter (e.g., "jellyfin", "firefly", "crush")

## Instructions

1. **Parse filter argument**:
   ```bash
   FILTER="${ARGUMENTS:-}"
   ```

2. **Query available work items**:

   If Supabase is available:
   ```sql
   SELECT
     work_item_id,
     integration_name,
     title,
     priority,
     required_skill_level,
     estimated_complexity
   FROM integration_work_items
   WHERE status = 'ready'
   ${FILTER:+AND integration_name = '$FILTER'}
   ORDER BY priority, created_at
   LIMIT 20;
   ```

3. **Display work items in table format**:
   ```
   | ID (short) | Integration | Title | Priority | Skill Level | Complexity |
   |------------|-------------|-------|----------|-------------|------------|
   | abc123     | jellyfin    | ...   | p1_high  | basic       | small      |
   ```

4. **Show summary**:
   - Total available items
   - Items by integration
   - Items by skill level

## Output Format

```
PMOVES-BoTZ Work Items Registry
==============================

Integration Filter: ${FILTER:-all}

Available Work Items (20 shown):

| ID       | Integration  | Title                          | Priority  | Skill    | Complexity |
|----------|--------------|--------------------------------|-----------|----------|------------|
| abc12345 | pmoves-crush | Fork upstream and create branch| p1_high   | basic    | small      |
| def67890 | jellyfin     | Create bridge API client       | p2_medium | tac      | medium     |

Summary:
- Total available: 15
- By integration: crush(8), jellyfin(3), firefly(2), wger(1), notebook(1)
- By skill level: basic(10), tac_enabled(3), mcp_augmented(2)

Use /workitems:claim <work_item_id> to claim a work item.
```

## Notes

- Only shows items with status='ready'
- Items are ordered by priority then creation date
- Shows first 20 items; use filter for specific integration
