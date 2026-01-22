create extension if not exists pgcrypto;
create extension if not exists "uuid-ossp";

create table if not exists chat_threads (
  id uuid primary key default gen_random_uuid(),
  title text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz default now()
);
create table if not exists chat_thread_members (
  thread_id uuid references chat_threads(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  role text default 'member',
  primary key (thread_id, user_id)
);
create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references chat_threads(id) on delete cascade,
  author_id uuid references auth.users(id) on delete set null,
  role text check (role in ('user','assistant','system','agent')) default 'user',
  text text,
  cgp jsonb,
  citations jsonb,
  status text default 'sent',
  created_at timestamptz default now(),
  updated_at timestamptz
);
create table if not exists notebook_entries (
  id uuid primary key default gen_random_uuid(),
  message_id uuid references chat_messages(id) on delete cascade,
  panel jsonb,
  edited_by uuid references auth.users(id) on delete set null,
  edited_at timestamptz default now()
);
create table if not exists ui_assets (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references auth.users(id) on delete set null,
  kind text check (kind in ('skin','avatar','bubble','sticker','other')),
  name text,
  version text,
  uri text,
  meta jsonb,
  created_at timestamptz default now()
);

alter table chat_threads enable row level security;
alter table chat_thread_members enable row level security;
alter table chat_messages enable row level security;
alter table notebook_entries enable row level security;
alter table ui_assets enable row level security;

create policy if not exists "members read thread" on chat_threads for select using (
  exists (select 1 from chat_thread_members m where m.thread_id = id and m.user_id = auth.uid())
);
create policy if not exists "members see members" on chat_thread_members for select using (
  user_id = auth.uid() or exists (select 1 from chat_thread_members m where m.thread_id = chat_thread_members.thread_id and m.user_id = auth.uid())
);
create policy if not exists "members read messages" on chat_messages for select using (
  exists (select 1 from chat_thread_members m where m.thread_id = chat_messages.thread_id and m.user_id = auth.uid())
);
create policy if not exists "members write messages" on chat_messages for insert with check (
  exists (select 1 from chat_thread_members m where m.thread_id = chat_messages.thread_id and m.user_id = auth.uid())
);
create policy if not exists "author can edit message" on chat_messages for update using (author_id = auth.uid()) with check (author_id = auth.uid());
create policy if not exists "members read notebook entries" on notebook_entries for select using (
  exists ( select 1 from chat_messages cm join chat_thread_members m on m.thread_id = cm.thread_id where cm.id = notebook_entries.message_id and m.user_id = auth.uid() )
);
create policy if not exists "members write notebook entries" on notebook_entries for insert with check (
  exists ( select 1 from chat_messages cm join chat_thread_members m on m.thread_id = cm.thread_id where cm.id = notebook_entries.message_id and m.user_id = auth.uid() )
);
create policy if not exists "owner manage assets" on ui_assets for all using (owner_id = auth.uid()) with check (owner_id = auth.uid());

create index if not exists chat_messages_thread_idx on chat_messages (thread_id, created_at desc);
create index if not exists notebook_entries_msg_idx on notebook_entries (message_id, edited_at desc);