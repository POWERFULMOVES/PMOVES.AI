create table if not exists view_groups (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references chat_threads(id) on delete cascade,
  name text,
  constraints jsonb,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz default now()
);
create table if not exists view_group_members (
  group_id uuid references view_groups(id) on delete cascade,
  message_id uuid references chat_messages(id) on delete cascade,
  primary key (group_id, message_id)
);
create table if not exists view_group_actions (
  id uuid primary key default gen_random_uuid(),
  group_id uuid references view_groups(id) on delete cascade,
  action text,
  params jsonb,
  applied_to_message_ids uuid[],
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz default now()
);

alter table view_groups enable row level security;
alter table view_group_members enable row level security;
alter table view_group_actions enable row level security;

create policy if not exists "members read groups" on view_groups for select using (
  exists (select 1 from chat_thread_members m where m.thread_id = view_groups.thread_id and m.user_id = auth.uid())
);
create policy if not exists "members write groups" on view_groups for insert with check (
  exists (select 1 from chat_thread_members m where m.thread_id = view_groups.thread_id and m.user_id = auth.uid())
);
create policy if not exists "members read group members" on view_group_members for select using (
  exists (select 1 from view_groups g join chat_thread_members m on m.thread_id = g.thread_id where g.id = view_group_members.group_id and m.user_id = auth.uid())
);
create policy if not exists "members write group members" on view_group_members for insert with check (
  exists (select 1 from view_groups g join chat_thread_members m on m.thread_id = g.thread_id where g.id = view_group_members.group_id and m.user_id = auth.uid())
);
create policy if not exists "members read group actions" on view_group_actions for select using (
  exists (select 1 from view_groups g join chat_thread_members m on m.thread_id = g.thread_id where g.id = view_group_actions.group_id and m.user_id = auth.uid())
);
create policy if not exists "members write group actions" on view_group_actions for insert with check (
  exists (select 1 from view_groups g join chat_thread_members m on m.thread_id = g.thread_id where g.id = view_group_actions.group_id and m.user_id = auth.uid())
);