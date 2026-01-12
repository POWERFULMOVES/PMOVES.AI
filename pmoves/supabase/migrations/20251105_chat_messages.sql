-- Chat messages for unified realtime chat in console
create table if not exists public.chat_messages (
  id bigserial primary key,
  owner_id uuid not null,
  role text not null default 'user', -- 'user' | 'agent'
  agent text,                       -- agent name when role='agent'
  avatar_url text,
  content text not null,
  created_at timestamp with time zone not null default now()
);

alter table public.chat_messages enable row level security;

-- Service role can do everything; browser reads and inserts are proxied via server APIs
do $$ begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='chat_messages' and policyname='chat_owner_read'
  ) then
    create policy chat_owner_read on public.chat_messages
      for select using (auth.role() = 'service_role' or auth.uid() = owner_id);
  end if;
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='chat_messages' and policyname='chat_owner_insert'
  ) then
    create policy chat_owner_insert on public.chat_messages
      for insert with check (auth.role() = 'service_role' or auth.uid() = owner_id);
  end if;
end $$;

create index if not exists idx_chat_owner_created on public.chat_messages(owner_id, created_at desc);

