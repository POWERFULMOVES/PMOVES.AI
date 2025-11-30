-- Named snapshots (enhanced)
create table if not exists snapshots (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references chat_threads(id) on delete cascade,
  name text not null,
  at timestamptz not null default now(),
  tags text[],
  position int,
  meta jsonb,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz default now()
);
alter table snapshots enable row level security;
create policy if not exists "members read snapshots" on snapshots for select using (
  exists (select 1 from chat_thread_members m where m.thread_id = snapshots.thread_id and m.user_id = auth.uid())
);
create policy if not exists "members write snapshots" on snapshots for insert with check (
  exists (select 1 from chat_thread_members m where m.thread_id = snapshots.thread_id and m.user_id = auth.uid())
);
create index if not exists snapshots_thread_idx on snapshots (thread_id, created_at desc);

-- Helper: latest view at/before time
create or replace function _latest_view_for_message(p_message_id uuid, p_cutoff timestamptz)
returns message_views language sql stable as $$
  select mv.* from message_views mv
  where mv.message_id = p_message_id and (p_cutoff is null or mv.created_at <= p_cutoff)
  order by mv.created_at desc limit 1
$$;

-- Atomic apply (translate/z_set/lock/visible/set_archetype_variant)
create or replace function rpc_apply_group_action(p_group_id uuid, p_action text, p_params jsonb, p_created_by uuid default auth.uid())
returns table(inserted_view_id uuid, message_id uuid) language plpgsql security definer as $$
declare rec record; msg_ids uuid[]; v_last message_views; v_new_layout jsonb;
v_locked boolean; v_visible boolean; v_z int; v_arch text; v_var text; v_seed int;
begin
  select array_agg(m.message_id) into msg_ids from view_group_members m where m.group_id = p_group_id;
  if msg_ids is null or array_length(msg_ids,1) is null then return; end if;
  for rec in
    select cm.id as message_id, (select id from content_blocks cb where cb.message_id = cm.id order by created_at desc limit 1) as block_id
    from chat_messages cm join unnest(msg_ids) mid on mid = cm.id
  loop
    if rec.block_id is null then continue; end if;
    v_last := _latest_view_for_message(rec.message_id, null);
    v_new_layout := coalesce(v_last.layout, '{}'::jsonb);
    v_locked := coalesce(v_last.locked,false);
    v_visible := coalesce(v_last.visible,true);
    v_z := coalesce(v_last.z,0);
    v_arch := coalesce(v_last.archetype,'speech.round');
    v_var := v_last.variant;

    if p_action='translate' then
      v_new_layout := jsonb_set(v_new_layout,'{x}',to_jsonb(coalesce((v_last.layout->>'x')::int,0) + coalesce((p_params->>'dx')::int,0)),true);
      v_new_layout := jsonb_set(v_new_layout,'{y}',to_jsonb(coalesce((v_last.layout->>'y')::int,0) + coalesce((p_params->>'dy')::int,0)),true);
    elsif p_action='z_set' then v_z := coalesce((p_params->>'z')::int, v_z);
    elsif p_action='lock' then v_locked := coalesce((p_params->>'value')::boolean, v_locked);
    elsif p_action='visible' then v_visible := coalesce((p_params->>'value')::boolean, v_visible);
    elsif p_action='set_archetype_variant' then v_arch := coalesce(p_params->>'archetype', v_arch); v_var := (p_params->>'variant');
    end if;

    v_seed := floor(random()*2147483647)::int;
    insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
    values (rec.message_id, rec.block_id, v_arch, v_var, v_seed, v_new_layout, coalesce(v_last.style,'{}'::jsonb), v_locked, v_visible, v_z, p_created_by)
    returning id, rec.message_id into inserted_view_id, message_id;
    return next;
  end loop;
  insert into view_group_actions (group_id, action, params, applied_to_message_ids, created_by) values (p_group_id, p_action, p_params, msg_ids, p_created_by);
end $$;

-- Layout ops: align/distribute/equalize (atomic)
create or replace function rpc_align_group(p_group_id uuid, p_mode text, p_created_by uuid default auth.uid())
returns void language plpgsql security definer as $$
declare msg_ids uuid[]; r record; minx int; maxx int; midx int; miny int; maxy int; midy int; last message_views; ax int; ay int;
begin
  select array_agg(m.message_id) into msg_ids from view_group_members m where m.group_id = p_group_id;
  if msg_ids is null or array_length(msg_ids,1) is null then return; end if;
  minx := 2147483647; miny := 2147483647; maxx := -2147483648; maxy := -2147483648;
  for r in select cm.id as message_id, _latest_view_for_message(cm.id,null) as last from chat_messages cm join unnest(msg_ids) u on u = cm.id loop
    last := r.last; if last.id is null then continue; end if;
    minx := least(minx, coalesce((last.layout->>'x')::int,0));
    miny := least(miny, coalesce((last.layout->>'y')::int,0));
    maxx := greatest(maxx, coalesce((last.layout->>'x')::int,0)+coalesce((last.layout->>'w')::int,320));
    maxy := greatest(maxy, coalesce((last.layout->>'y')::int,0)+coalesce((last.layout->>'h')::int,200));
  end loop;
  midx := (minx+maxx)/2; midy := (miny+maxy)/2;

  for r in select cm.id as message_id, (select id from content_blocks where message_id=cm.id order by created_at desc limit 1) as block_id, _latest_view_for_message(cm.id,null) as last from chat_messages cm join unnest(msg_ids) u on u=cm.id loop
    last := r.last; if last.id is null or r.block_id is null then continue; end if;
    ax := coalesce((last.layout->>'x')::int,0);
    ay := coalesce((last.layout->>'y')::int,0);
    if p_mode='left' then ax := minx; end if;
    if p_mode='right' then ax := maxx - coalesce((last.layout->>'w')::int,320); end if;
    if p_mode='center' then ax := midx - coalesce((last.layout->>'w')::int,320)/2; end if;
    if p_mode='top' then ay := miny; end if;
    if p_mode='bottom' then ay := maxy - coalesce((last.layout->>'h')::int,200); end if;
    if p_mode='middle' then ay := midy - coalesce((last.layout->>'h')::int,200)/2; end if;
    insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
    values (r.message_id, r.block_id, coalesce(last.archetype,'speech.round'), last.variant, floor(random()*2147483647)::int,
      jsonb_set(jsonb_set(coalesce(last.layout,'{}'::jsonb), '{x}', to_jsonb(ax), true), '{y}', to_jsonb(ay), true),
      coalesce(last.style,'{}'::jsonb), coalesce(last.locked,false), coalesce(last.visible,true), coalesce(last.z,0), p_created_by);
  end loop;
  insert into view_group_actions (group_id, action, params, applied_to_message_ids, created_by) values (p_group_id, 'align', jsonb_build_object('mode',p_mode), msg_ids, p_created_by);
end $$;

create or replace function rpc_distribute_group(p_group_id uuid, p_axis text, p_created_by uuid default auth.uid())
returns void language plpgsql security definer as $$
declare msg_ids uuid[]; arr jsonb := '[]'::jsonb; rec record; sorted jsonb[]; i int; minpos int; maxpos int; total int; space numeric; last message_views; pos int;
begin
  select array_agg(m.message_id) into msg_ids from view_group_members m where m.group_id = p_group_id;
  if msg_ids is null or array_length(msg_ids,1) is null then return; end if;
  for rec in select cm.id, _latest_view_for_message(cm.id,null) as last from chat_messages cm join unnest(msg_ids) u on u=cm.id loop
    last := rec.last; if last.id is null then continue; end if;
    arr := arr || jsonb_build_object('id',rec.id,'x',coalesce((last.layout->>'x')::int,0),'y',coalesce((last.layout->>'y')::int,0),'w',coalesce((last.layout->>'w')::int,320),'h',coalesce((last.layout->>'h')::int,200));
  end loop;
  if jsonb_array_length(arr) < 3 then return; end if;
  if p_axis='h' then
    sorted := (select array_agg(value order by (value->>'x')::int) from jsonb_array_elements(arr));
    minpos := (sorted[1]->>'x')::int;
    maxpos := (select max((value->>'x')::int + (value->>'w')::int) from unnest(sorted) v(value));
    total := (select sum((value->>'w')::int) from unnest(sorted) v(value));
  else
    sorted := (select array_agg(value order by (value->>'y')::int) from jsonb_array_elements(arr));
    minpos := (sorted[1]->>'y')::int;
    maxpos := (select max((value->>'y')::int + (value->>'h')::int) from unnest(sorted) v(value));
    total := (select sum((value->>'h')::int) from unnest(sorted) v(value));
  end if;
  space := (maxpos - minpos - total)::numeric / (jsonb_array_length(arr) - 1);
  for i in 2..jsonb_array_length(arr)-1 loop
    last := _latest_view_for_message((sorted[i]->>'id')::uuid,null);
    if p_axis='h' then pos := minpos + ((i-1) * space)::int; insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
      values (last.message_id, last.block_id, coalesce(last.archetype,'speech.round'), last.variant, floor(random()*2147483647)::int, jsonb_set(coalesce(last.layout,'{}'::jsonb), '{x}', to_jsonb(pos), true), coalesce(last.style,'{}'::jsonb), coalesce(last.locked,false), coalesce(last.visible,true), coalesce(last.z,0), p_created_by);
    else pos := minpos + ((i-1) * space)::int; insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
      values (last.message_id, last.block_id, coalesce(last.archetype,'speech.round'), last.variant, floor(random()*2147483647)::int, jsonb_set(coalesce(last.layout,'{}'::jsonb), '{y}', to_jsonb(pos), true), coalesce(last.style,'{}'::jsonb), coalesce(last.locked,false), coalesce(last.visible,true), coalesce(last.z,0), p_created_by);
    end if;
  end loop;
  insert into view_group_actions (group_id, action, params, applied_to_message_ids, created_by) values (p_group_id, 'distribute', jsonb_build_object('axis',p_axis), msg_ids, p_created_by);
end $$;

create or replace function rpc_equalize_group(p_group_id uuid, p_what text, p_created_by uuid default auth.uid())
returns void language plpgsql security definer as $$
declare msg_ids uuid[]; ref message_views; rec record; new_w int; new_h int; last message_views;
begin
  select array_agg(m.message_id) into msg_ids from view_group_members m where m.group_id = p_group_id;
  if msg_ids is null or array_length(msg_ids,1) is null then return; end if;
  for rec in select cm.id from chat_messages cm join unnest(msg_ids) u on u=cm.id limit 1 loop ref := _latest_view_for_message(rec.id,null); end loop;
  if ref.id is null then return; end if;
  new_w := coalesce((ref.layout->>'w')::int,320); new_h := coalesce((ref.layout->>'h')::int,200);
  for rec in select cm.id as message_id, (select id from content_blocks where message_id=cm.id order by created_at desc limit 1) as block_id, _latest_view_for_message(cm.id,null) as last from chat_messages cm join unnest(msg_ids) u on u=cm.id loop
    last := rec.last; if last.id is null then continue; end if;
    insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
    values (rec.message_id, rec.block_id, coalesce(last.archetype,'speech.round'), last.variant, floor(random()*2147483647)::int,
      case when p_what='w' then jsonb_set(coalesce(last.layout,'{}'::jsonb), '{w}', to_jsonb(new_w), true)
           when p_what='h' then jsonb_set(coalesce(last.layout,'{}'::jsonb), '{h}', to_jsonb(new_h), true)
           else jsonb_set(jsonb_set(coalesce(last.layout,'{}'::jsonb), '{w}', to_jsonb(new_w), true), '{h}', to_jsonb(new_h), true) end,
      coalesce(last.style,'{}'::jsonb), coalesce(last.locked,false), coalesce(last.visible,true), coalesce(last.z,0), p_created_by);
  end loop;
  insert into view_group_actions (group_id, action, params, applied_to_message_ids, created_by) values (p_group_id, 'equalize', jsonb_build_object('what',p_what), msg_ids, p_created_by);
end $$;

-- Rotate/Scale
create or replace function rpc_rotate_group(p_group_id uuid, p_degrees int, p_created_by uuid default auth.uid())
returns void language plpgsql security definer as $$
declare msg_ids uuid[]; r record; last message_views;
begin
  select array_agg(m.message_id) into msg_ids from view_group_members m where m.group_id = p_group_id;
  if msg_ids is null or array_length(msg_ids,1) is null then return; end if;
  for r in select cm.id as message_id, (select id from content_blocks cb where cb.message_id=cm.id order by created_at desc limit 1) as block_id, _latest_view_for_message(cm.id,null) as last from chat_messages cm join unnest(msg_ids) u on u=cm.id loop
    last := r.last; if last.id is null or r.block_id is null then continue; end if;
    insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
    values (r.message_id, r.block_id, coalesce(last.archetype,'speech.round'), last.variant, floor(random()*2147483647)::int,
      jsonb_set(coalesce(last.layout,'{}'::jsonb), '{rotation}', to_jsonb(coalesce((last.layout->>'rotation')::int,0) + p_degrees), true),
      coalesce(last.style,'{}'::jsonb), coalesce(last.locked,false), coalesce(last.visible,true), coalesce(last.z,0), p_created_by);
  end loop;
  insert into view_group_actions (group_id, action, params, applied_to_message_ids, created_by) values (p_group_id, 'rotate', jsonb_build_object('degrees',p_degrees), msg_ids, p_created_by);
end $$;

create or replace function rpc_scale_group(p_group_id uuid, p_factor numeric, p_created_by uuid default auth.uid())
returns void language plpgsql security definer as $$
declare msg_ids uuid[]; r record; last message_views; nw int; nh int;
begin
  select array_agg(m.message_id) into msg_ids from view_group_members m where m.group_id = p_group_id;
  if msg_ids is null or array_length(msg_ids,1) is null then return; end if;
  for r in select cm.id as message_id, (select id from content_blocks cb where cb.message_id=cm.id order by created_at desc limit 1) as block_id, _latest_view_for_message(cm.id,null) as last from chat_messages cm join unnest(msg_ids) u on u=cm.id loop
    last := r.last; if last.id is null or r.block_id is null then continue; end if;
    nw := greatest(0, round(coalesce((last.layout->>'w')::numeric,320)*p_factor))::int;
    nh := greatest(0, round(coalesce((last.layout->>'h')::numeric,200)*p_factor))::int;
    insert into message_views (message_id, block_id, archetype, variant, seed, layout, style, locked, visible, z, created_by)
    values (r.message_id, r.block_id, coalesce(last.archetype,'speech.round'), last.variant, floor(random()*2147483647)::int,
      jsonb_set(jsonb_set(coalesce(last.layout,'{}'::jsonb), '{w}', to_jsonb(nw), true), '{h}', to_jsonb(nh), true),
      coalesce(last.style,'{}'::jsonb), coalesce(last.locked,false), coalesce(last.visible,true), coalesce(last.z,0), p_created_by);
  end loop;
  insert into view_group_actions (group_id, action, params, applied_to_message_ids, created_by) values (p_group_id, 'scale', jsonb_build_object('factor',p_factor), msg_ids, p_created_by);
end $$;

-- Snapshots: ticks and snapshot at time
create or replace function rpc_snapshot_ticks(p_thread_id uuid, p_limit int default 200)
returns table(tick timestamptz, source text, id uuid) language sql stable as $$
  select created_at as tick, 'view'::text as source, id from message_views mv
  where exists(select 1 from chat_messages cm where cm.id = mv.message_id and cm.thread_id = p_thread_id)
  union all
  select created_at as tick, 'action'::text as source, id from view_group_actions ga
  where exists(select 1 from view_groups g where g.id = ga.group_id and g.thread_id = p_thread_id)
  order by tick desc limit p_limit
$$;

create or replace function rpc_snapshot_views(p_thread_id uuid, p_at timestamptz)
returns table(message_id uuid, view_id uuid, block_id uuid, archetype text, variant text, seed int, layout jsonb, style jsonb, locked boolean, visible boolean, z int, created_at timestamptz)
language sql stable as $$
  with msgs as (select id from chat_messages where thread_id = p_thread_id)
  select m.id as message_id, v.id as view_id, v.block_id, v.archetype, v.variant, v.seed, v.layout, v.style, v.locked, v.visible, v.z, v.created_at
  from msgs m
  left join lateral (
    select * from message_views mv where mv.message_id = m.id and (p_at is null or mv.created_at <= p_at)
    order by created_at desc limit 1
  ) v on true
  order by coalesce(v.z,0), v.created_at desc nulls last
$$;