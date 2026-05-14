-- IT error records extracted from logs/XML/text
create table if not exists it_errors (
  id bigserial primary key,
  doc_id text,
  namespace text,
  tag text,
  message text,
  code text,
  service text,
  host text,
  severity text,
  timestamp text,
  stack text,
  created_at timestamptz default now()
);

-- Hardened: no anon access to error records
grant select on table it_errors to authenticated;
grant all on table it_errors to service_role;

alter table it_errors enable row level security;

-- Drop permissive anon policy
do $$ begin
  drop policy if exists it_errors_anon_all on it_errors;
exception when others then null; end $$;

-- Authenticated: read-only
create policy it_errors_auth_read on it_errors
  for select to authenticated using (true);

-- Service role: full access
create policy it_errors_svc_all on it_errors
  for all to service_role using (true) with check (true);
