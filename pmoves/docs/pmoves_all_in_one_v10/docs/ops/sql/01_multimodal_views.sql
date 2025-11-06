create table if not exists content_blocks (
  id uuid primary key default gen_random_uuid(),
  message_id uuid references chat_messages(id) on delete cascade,
  kind text check (kind in ('text','audio','image','video','3d','data')),
  uri text,
  meta jsonb,
  created_at timestamptz default now()
);
create table if not exists message_views (
  id uuid primary key default gen_random_uuid(),
  message_id uuid references chat_messages(id) on delete cascade,
  block_id uuid references content_blocks(id) on delete cascade,
  archetype text,
  variant text,
  seed int,
  layout jsonb,
  style jsonb,
  created_by uuid references auth.users(id),
  created_at timestamptz default now(),
  locked boolean default false,
  visible boolean default true,
  z int default 0
);

alter table content_blocks enable row level security;
alter table message_views enable row level security;

create policy if not exists "members read blocks" on content_blocks for select using (
  exists (select 1 from chat_messages cm join chat_thread_members m on m.thread_id = cm.thread_id where cm.id = content_blocks.message_id and m.user_id = auth.uid())
);
create policy if not exists "members write blocks" on content_blocks for insert with check (
  exists (select 1 from chat_messages cm join chat_thread_members m on m.thread_id = cm.thread_id where cm.id = content_blocks.message_id and m.user_id = auth.uid())
);
create policy if not exists "members read views" on message_views for select using (
  exists (select 1 from chat_messages cm join chat_thread_members m on m.thread_id = cm.thread_id where cm.id = message_views.message_id and m.user_id = auth.uid())
);
create policy if not exists "members write views" on message_views for insert with check (
  exists (select 1 from chat_messages cm join chat_thread_members m on m.thread_id = cm.thread_id where cm.id = message_views.message_id and m.user_id = auth.uid())
);

create index if not exists content_blocks_msg_idx on content_blocks (message_id, created_at desc);
create index if not exists message_views_msg_idx on message_views (message_id, created_at desc);
create index if not exists message_views_z_idx on message_views (message_id, z);