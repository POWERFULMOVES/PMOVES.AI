-- PMOVES Core: tool docs catalog for yt-dlp and others
create schema if not exists pmoves_core;

create table if not exists pmoves_core.tool_docs (
  tool text not null,
  version text not null,
  doc_type text not null,
  content jsonb not null,
  created_at timestamptz not null default now(),
  primary key (tool, version, doc_type)
);

grant usage on schema pmoves_core to anon, authenticated, service_role;
grant select, insert, update on pmoves_core.tool_docs to anon, authenticated, service_role;

