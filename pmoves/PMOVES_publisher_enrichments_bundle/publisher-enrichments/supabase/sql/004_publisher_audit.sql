-- 004_publisher_audit.sql
create table if not exists publisher_audit (
  id bigserial primary key,
  studio_id bigint references studio_board(id) on delete cascade,
  action text not null,         -- e.g., 'notify.discord', 'jellyfin.refresh', 'error'
  payload jsonb,                -- details (webhook response, error, etc.)
  created_at timestamptz default now()
);

create index if not exists idx_pub_audit_studio on publisher_audit(studio_id);
