import React, { useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase";
export function SnapshotBookmarksPro({ threadId, onPick }:{ threadId:string; onPick:(iso:string)=>void }){
  const [items,setItems]=useState<any[]>([]); const [query,setQuery]=useState(""); const [name,setName]=useState(""); const [tags,setTags]=useState<string>(""); const [dragId,setDragId]=useState<string|undefined>();
  async function load(){ const { data } = await supabase.from("snapshots").select("*").eq("thread_id",threadId).order("position",{ascending:true}).order("created_at",{ascending:false}); setItems(data||[]); }
  useEffect(()=>{ if(threadId) load(); },[threadId]);
  async function add(){ if(!name) return; const tagList = tags.split(",").map(s=>s.trim()).filter(Boolean); const pos = (items[items.length-1]?.position || 0) + 1; const { error } = await supabase.from("snapshots").insert({ thread_id:threadId, name, at:new Date().toISOString(), tags:tagList, position:pos }); if(!error){ setName(""); setTags(""); await load(); } }
  async function swap(a:any,b:any){ await supabase.from("snapshots").update({ position:b.position }).eq("id",a.id); await supabase.from("snapshots").update({ position:a.position }).eq("id",b.id); await load(); }
  function onDragStart(e:any, id:string){ setDragId(id); e.dataTransfer.effectAllowed="move"; }
  function onDragOver(e:any, id:string){ e.preventDefault(); e.dataTransfer.dropEffect="move"; }
  function onDrop(e:any, id:string){ e.preventDefault(); if(!dragId || dragId===id) return; const from=items.find(x=>x.id===dragId), to=items.find(x=>x.id===id); if(from && to) swap(from,to); setDragId(undefined); }
  const filtered = useMemo(()=>{ const q=query.toLowerCase(); return items.filter(s=>!q || s.name.toLowerCase().includes(q) || (s.tags||[]).some((t:string)=>t.toLowerCase().includes(q))); },[items,query]);
  return (<div style={{ border:"1px solid #333", borderRadius:8, padding:12, display:"grid", gap:8 }}>
    <h3 style={{margin:0}}>Snapshot Bookmarks (Pro)</h3>
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8 }}>
      <input placeholder="Search name or tag…" value={query} onChange={e=>setQuery(e.target.value)} />
      <div style={{ display:"flex", gap:8 }}><input placeholder="New snapshot name" value={name} onChange={e=>setName(e.target.value)} /><input placeholder="tags (comma)" value={tags} onChange={e=>setTags(e.target.value)} /><button onClick={add}>Add</button></div>
    </div>
    <ul style={{ listStyle:"none", padding:0, margin:0, display:"flex", flexDirection:"column", gap:6, maxHeight:240, overflowY:"auto" }}>
      {filtered.map((s:any)=>(<li key={s.id} draggable onDragStart={(e)=>onDragStart(e,s.id)} onDragOver={(e)=>onDragOver(e,s.id)} onDrop={(e)=>onDrop(e,s.id)} style={{ display:"grid", gridTemplateColumns:"1fr auto", gap:8, alignItems:"center", border: dragId===s.id? "1px dashed #ffd400":"1px solid #333", borderRadius:6, padding:6 }}>
        <button onClick={()=>onPick(s.at)} style={{ textAlign:"left" }}>{s.name} <span style={{ opacity:0.6, fontSize:12 }}>({new Date(s.at).toLocaleString()})</span>{(s.tags||[]).length ? <span style={{ marginLeft:8, opacity:0.7 }}>{s.tags.map((t:string)=>`#${t}`).join(" ")}</span> : null}</button>
        <small style={{ opacity:0.6 }}>pos {s.position ?? "—"}</small>
      </li>))}
    </ul>
  </div>);
}