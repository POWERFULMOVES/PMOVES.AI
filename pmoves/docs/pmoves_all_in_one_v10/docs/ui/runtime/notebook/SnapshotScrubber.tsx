import React, { useEffect, useMemo, useState } from "react";
import { useSnapshots } from "./useSnapshots";
import { supabase } from "@/lib/supabase";
export function SnapshotScrubber({ threadId, onChange }:{ threadId:string; onChange:(iso:string)=>void }){
  const { ticks, refreshTicks } = useSnapshots(threadId); const [idx,setIdx]=useState(0);
  useEffect(()=>{ if(!threadId) return; const ch=supabase.channel(`scrubber:${threadId}`); ch.on('postgres_changes',{ event:'*', schema:'public', table:'message_views' },()=>refreshTicks()); ch.on('postgres_changes',{ event:'*', schema:'public', table:'view_group_actions' },()=>refreshTicks()); ch.subscribe(); return ()=>{ ch.unsubscribe(); }; },[threadId]);
  useEffect(()=>{ if(ticks.length) onChange(ticks[idx]?.tick); },[idx,ticks]);
  const labels = useMemo(()=> ticks.map(t=>new Date(t.tick).toLocaleTimeString()),[ticks]); const max=Math.max(0,ticks.length-1);
  return (<div style={{ border:"1px solid #333", borderRadius:8, padding:12 }}><div style={{ display:"flex", gap:8, alignItems:"center" }}>
    <input type="range" min={0} max={max} value={idx} onChange={e=>setIdx(Number(e.target.value))} style={{ flex:1 }} /><span style={{ fontVariantNumeric:"tabular-nums" }}>{labels[idx]||"—"}</span></div><small>{ticks.length} ticks</small></div>);
}