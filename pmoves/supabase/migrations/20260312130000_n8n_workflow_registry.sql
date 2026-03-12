create schema if not exists pmoves_core;

create table if not exists pmoves_core.n8n_workflow_registry (
    workflow_id text primary key,
    workflow_name text not null,
    canonical_filename text,
    canonical_path text,
    source_repo text not null default 'PMOVES-n8n',
    source_submodule_path text not null default 'PMOVES-n8n/workflows',
    target_active boolean not null default false,
    is_active boolean not null default false,
    version_id uuid,
    active_version_id uuid,
    project_id text,
    nodes_count integer not null default 0,
    tags jsonb not null default '[]'::jsonb,
    sync_meta jsonb not null default '{}'::jsonb,
    last_synced_at timestamptz not null default timezone('utc', now())
);

create index if not exists n8n_workflow_registry_is_active_idx
    on pmoves_core.n8n_workflow_registry (is_active);

create index if not exists n8n_workflow_registry_target_active_idx
    on pmoves_core.n8n_workflow_registry (target_active);

grant usage on schema pmoves_core to authenticated, service_role;
grant select on pmoves_core.n8n_workflow_registry to authenticated;
grant select, insert, update, delete on pmoves_core.n8n_workflow_registry to service_role;

alter table pmoves_core.n8n_workflow_registry enable row level security;

drop policy if exists "n8n workflow registry read" on pmoves_core.n8n_workflow_registry;
create policy "n8n workflow registry read"
    on pmoves_core.n8n_workflow_registry
    for select
    to authenticated
    using (true);

drop policy if exists "n8n workflow registry service write" on pmoves_core.n8n_workflow_registry;
create policy "n8n workflow registry service write"
    on pmoves_core.n8n_workflow_registry
    for all
    to service_role
    using (true)
    with check (true);

comment on table pmoves_core.n8n_workflow_registry is
    'Live n8n workflow inventory synced from PMOVES-n8n via the n8n Public API.';
