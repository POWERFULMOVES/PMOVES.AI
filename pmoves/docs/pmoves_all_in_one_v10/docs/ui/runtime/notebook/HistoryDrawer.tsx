import React from "react";
import type { MessageView } from "./useSupabaseViews";
export function HistoryDrawer({ views, onPick }:{ views:MessageView[]; onPick:(v:MessageView)=>void; }){
  return (<div style={{ borderLeft:"1px solid #333", paddingLeft:12 }}><h3 style={{ marginTop:0 }}>History</h3>
    <ol style={{ listStyle:"none", padding:0, margin:0, display:"flex", flexDirection:"column", gap:8, maxHeight:360, overflowY:"auto" }}>
      {views.map(v=>(<li key={v.id}><button onClick={()=>onPick(v)} style={{ display:"flex", gap:8, alignItems:"center", width:"100%" }}><code style={{ fontSize:12 }}>{v.archetype}</code><span style={{ opacity:0.8 }}>{v.variant||"default"}</span><span style={{ marginLeft:"auto", opacity:0.6 }}>seed {v.seed ?? "—"}</span></button></li>))}
    </ol><small>Click to load its properties; saving appends a new view.</small></div>);
}