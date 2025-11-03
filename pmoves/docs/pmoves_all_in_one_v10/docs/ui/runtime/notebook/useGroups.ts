import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
export type ViewGroup = { id:string; thread_id:string; name:string; constraints?:any; created_at:string };
export type ViewGroupAction = { id:string; group_id:string; action:string; params:any; applied_to_message_ids:string[]; created_at:string };
export function useGroups(threadId:string){
  const [groups,setGroups]=useState<ViewGroup[]>([]);
  const [members,setMembers]=useState<Record<string,string[]>>({});
  const [actions,setActions]=useState<Record<string,ViewGroupAction[]>>({});
  const [loading,setLoading]=useState(false); const [error,setError]=useState<string|null>(null);
  useEffect(()=>{ let alive=true;(async()=>{
    if(!threadId) return; setLoading(true);
    const { data:gs, error:e1 } = await supabase.from('view_groups').select('*').eq('thread_id',threadId).order('created_at',{ ascending:true });
    if(e1){ if(alive) setError(e1.message); return; } setGroups(gs||[]);
    const gids=(gs||[]).map(g=>g.id);
    if(gids.length){ const { data:mem } = await supabase.from('view_group_members').select('*').in('group_id',gids);
      const mp:Record<string,string[]>={}; (mem||[]).forEach((m:any)=>{ (mp[m.group_id] ||= []).push(m.message_id); }); setMembers(mp);
      const { data:acts } = await supabase.from('view_group_actions').select('*').in('group_id',gids).order('created_at',{ ascending:true });
      const ap:Record<string,ViewGroupAction[]>={}; (acts||[]).forEach((a:any)=>{ (ap[a.group_id] ||= []).push(a); }); setActions(ap);
    } setLoading(false);
    const ch = supabase.channel(`groups:${threadId}`);
    ch.on('postgres_changes',{ event:'*', schema:'public', table:'view_groups' },p=>{ const g=p.new as any; if(g?.thread_id!==threadId) return; setGroups(prev=>{ const arr=prev.slice(); if(p.eventType==='INSERT') arr.push(g); else if(p.eventType==='UPDATE'){ const i=arr.findIndex(x=>x.id===g.id); if(i>=0) arr[i]=g; } else if(p.eventType==='DELETE'){ return arr.filter(x=>x.id !== p.old.id); } return arr; }); });
    ch.on('postgres_changes',{ event:'*', schema:'public', table:'view_group_members' },p=>{ const m=p.new as any; setMembers(prev=>{ const mp={...prev}; const gid=m.group_id||p.old?.group_id; if(!gid) return mp; const set=new Set(mp[gid]||[]); if(p.eventType==='INSERT'&&m?.message_id) set.add(m.message_id); if(p.eventType==='DELETE'&&p.old?.message_id) set.delete(p.old.message_id); mp[gid]=Array.from(set); return mp; }); });
    ch.on('postgres_changes',{ event:'*', schema:'public', table:'view_group_actions' },p=>{ const a=p.new as any; setActions(prev=>{ const ap={...prev}; const gid=a.group_id||p.old?.group_id; if(!gid) return ap; const list=(ap[gid]||[]).slice(); if(p.eventType==='INSERT') list.push(a); ap[gid]=list; return ap; }); });
    ch.subscribe(); return ()=>{ ch.unsubscribe(); };
  })(); return ()=>{ alive=false }; },[threadId]);
  async function createGroup(name:string, constraints?:any){ const { data, error }=await supabase.from('view_groups').insert({ thread_id:threadId, name, constraints: constraints||null }).select('*').single(); if(error) throw error; return data as any; }
  async function renameGroup(id:string, name:string){ const { error } = await supabase.from('view_groups').update({ name }).eq('id',id); if(error) throw error; }
  async function deleteGroup(id:string){ const { error } = await supabase.from('view_groups').delete().eq('id',id); if(error) throw error; }
  async function addMember(groupId:string, messageId:string){ const { error } = await supabase.from('view_group_members').insert({ group_id:groupId, message_id:messageId }); if(error) throw error; }
  async function removeMember(groupId:string, messageId:string){ const { error } = await supabase.from('view_group_members').delete().match({ group_id:groupId, message_id:messageId }); if(error) throw error; }
  async function logAction(groupId:string, action:string, params:any, appliedTo:string[]){ const { error } = await supabase.from('view_group_actions').insert({ group_id:groupId, action, params, applied_to_message_ids: appliedTo }); if(error) throw error; }
  return { groups, members, actions, loading, error, createGroup, renameGroup, deleteGroup, addMember, removeMember, logAction };
}