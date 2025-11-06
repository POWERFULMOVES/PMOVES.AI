import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
export type Message = { id:string; thread_id:string; text:string; cgp?:any; created_at:string };
export type ContentBlock = { id:string; message_id:string; kind:string; uri:string; meta?:any };
export type MessageView = { id?:string; message_id:string; block_id:string; archetype:string; variant?:string; seed?:number; layout?:any; style?:any; locked?:boolean; visible?:boolean; z?:number; created_by?:string; created_at?:string; };
export function useSupabaseViews(threadId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [blocks, setBlocks] = useState<Record<string, ContentBlock[]>>({});
  const [views, setViews] = useState<Record<string, MessageView[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string|null>(null);
  useEffect(()=>{ let alive=true; (async()=>{
    if (!threadId) return;
    setLoading(true);
    const { data: msgs, error: e1 } = await supabase.from('chat_messages').select('id,thread_id,text,cgp,created_at').eq('thread_id', threadId).order('created_at', { ascending: true });
    if (e1) { if(alive) setError(e1.message); return; }
    setMessages(msgs||[]);
    const ids = (msgs||[]).map(m=>m.id);
    const { data: blks } = await supabase.from('content_blocks').select('*').in('message_id', ids);
    const bmap: Record<string, ContentBlock[]> = {}; (blks||[]).forEach(b=>{ (bmap[b.message_id] ||= []).push(b); }); setBlocks(bmap);
    const { data: vws } = await supabase.from('message_views').select('*').in('message_id', ids).order('created_at', { ascending: true });
    const vmap: Record<string, MessageView[]> = {}; (vws||[]).forEach(v=>{ (vmap[v.message_id] ||= []).push(v as any); }); setViews(vmap); setLoading(false);
    const ch = supabase.channel(`views:${threadId}`);
    ch.on('postgres_changes',{ event:'*', schema:'public', table:'message_views' },(p)=>{ const v = p.new as any; setViews(prev=>{ const arr=(prev[v.message_id]||[]).slice(); const idx=arr.findIndex(x=>x.id===v.id); if (p.eventType==='INSERT') arr.push(v); else if (p.eventType==='UPDATE'&&idx>=0) arr[idx]=v; return { ...prev, [v.message_id]: arr }; }); });
    ch.subscribe(); return ()=>{ ch.unsubscribe(); };
  })(); return ()=>{ alive=false }; },[threadId]);
  const latestViewOf = (messageId:string)=>{ const arr=views[messageId]||[]; return arr.length?arr[arr.length-1]:undefined; };
  async function saveNewView(v: MessageView){
    const payload:any = { message_id:v.message_id, block_id:v.block_id, archetype:v.archetype, variant:v.variant||null, seed:v.seed||null, layout:v.layout||null, style:v.style||null, locked:v.locked??false, visible:v.visible??true, z:v.z??0 };
    const { error:e } = await supabase.from('message_views').insert(payload); if (e) throw e;
  }
  return { messages, blocks, views, latestViewOf, saveNewView, loading, error };
}