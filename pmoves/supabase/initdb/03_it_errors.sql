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
grant select, insert, update, delete on table it_errors to anon;
alter table it_errors enable row level security;
do $$ begin
  create policy it_errors_anon_all on it_errors for all to anon using (true) with check (true);
exception when duplicate_object then null; end $$;
