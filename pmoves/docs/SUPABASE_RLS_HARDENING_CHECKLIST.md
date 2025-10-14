# Supabase RLS Hardening Checklist
_Last updated: 2025-10-14_

This checklist catalogs the steps required to transition PMOVES from dev-mode Supabase policies to production-quality Row Level Security (RLS) for the creator/publisher workflows.

## Prerequisites
- Supabase CLI connected to the target project (`supabase start` or configured remote).
- Service role key accessible for administrative updates.
- Latest schema migrations applied (`supabase db push` or `make supabase-migrate`). 
- A staging Discord webhook and Agent Zero stack available for smoke validation.

## Tables & Views in Scope
| Table/View | Notes |
| --- | --- |
| `studio_board` | Approval lifecycle (`draft` → `approved` → `published`). Guarantees that only the owner or automation can mutate publish state. |
| `publisher_rollup` | Stores telemetry, cost, and turnaround metrics. Should remain service-role only. |
| `publisher_discord_metrics` | Discord delivery audit. Readable by analysts, writeable only by automation. |
| `publisher_failures` | Error diagnostics; service-role only with optional viewer role. |
| `archon_prompts` / `archon_task_history` | Guard cross-tenant reads when multi-user sharing lands. |
| `geometry_cgp_packets` / `geometry_constellations` | Protect geometry dumps once external users gain access. |

## Policy Matrix
| Actor | `studio_board` | `publisher_rollup` | `publisher_discord_metrics` |
| --- | --- | --- | --- |
| **Service Role** | Full control | Full control | Full control |
| **Automation (Agent Zero)** | Insert publish events via `rpc_publish_content` | Insert only | Insert only |
| **Authenticated Creator** | `select` + `update` on own rows (`created_by`) | Read-only (optional) | Read-only (optional) |
| **Anonymous** | No access | No access | No access |

## Implementation Steps
1. **Enable RLS**  
   ```sql
   alter table studio_board enable row level security;
   alter table publisher_rollup enable row level security;
   alter table publisher_discord_metrics enable row level security;
   ```

2. **Define Policies**
   ```sql
   -- studio_board: owners can read/write their rows
   create policy studio_board_owner_policy
     on studio_board
     for all
     using (auth.uid() = created_by)
     with check (auth.uid() = created_by);

   -- studio_board: automation (service role) can publish
   create policy studio_board_publish_policy
     on studio_board
     for update
     using (auth.role() = 'service_role');

   -- publisher_rollup: service role only
   create policy publisher_rollup_rw_service
     on publisher_rollup
     for all
     using (auth.role() = 'service_role')
     with check (auth.role() = 'service_role');

   -- publisher_discord_metrics: analysts read, service role writes
   create policy publisher_discord_read_analyst
     on publisher_discord_metrics
     for select
     using (auth.role() in ('service_role', 'analytics'));
   create policy publisher_discord_write_service
     on publisher_discord_metrics
     for all
     using (auth.role() = 'service_role')
     with check (auth.role() = 'service_role');
   ```

3. **Role Provisioning**
   ```sql
   create role analytics;
   grant usage on schema public to analytics;
   grant select on publisher_discord_metrics to analytics;
   ```

4. **Audit Functions**
   - Add default values (`updated_at` triggers) so service-role updates leave an audit trail.
   - Consider `log_rls()` helper to capture denied requests during rollout.

5. **Automated Tests**
   - Extend `scripts/check_chit_contract.sh` or add `scripts/check_rls.py` to run Supabase RPCs verifying policy outcomes.
   - Run inside CI before deploying migrations.

## Validation Plan
1. Run the Supabase test harness: `python tools/rls_smoke.py --env dev`.  
2. Use the n8n poller to perform a publish and confirm service-role writes to `publisher_rollup` still succeed.  
3. Attempt to fetch `studio_board` rows using an anon key (expect 401/403).  
4. Attempt to update another user's row using a non-owner JWT (expect RLS denial).  
5. Confirm analytics role can query `publisher_discord_metrics` but cannot modify data.

## Rollout Checklist
- [ ] Apply policies in staging project.  
- [ ] Run automated test suite.  
- [ ] Capture Supabase audit logs to ensure no unexpected denies.  
- [ ] Update `db/migrations` with the new policies.  
- [ ] Repeat in production after sign-off.
