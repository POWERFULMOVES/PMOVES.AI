import React, { useMemo, useState } from "react";
import { useSnapshots } from "./useSnapshots";
import { MultiViewEditor } from "./MultiViewEditor";
export function SnapshotBrowser({ threadId, toLayers, onPersist }:{ threadId:string; toLayers:(views:any[])=>any[]; onPersist:(views:any[])=>Promise<void>; }){
  const { ticks, fetchSnapshot, loading, error } = useSnapshots(threadId);
  const [selected,setSelected]=useState<string>(""); const [snapshot,setSnapshot]=useState<any[]>([]); const [busy,setBusy]=useState(false);
  const marks = useMemo(()=> ticks.map(t=>({ at:t.tick, label:new Date(t.tick).toLocaleString() })),[ticks]);
  async function load(){ if(!selected) return; const views = await fetchSnapshot(selected); setSnapshot(views); }
  async function persist(){ setBusy(true); try{ await onPersist(snapshot); } finally { setBusy(false); } }
  return (<div style={{ display:"grid", gap:12 }}>
    <div style={{ display:"flex", gap:8, alignItems:"center" }}>
      <select value={selected} onChange={e=>setSelected(e.target.value)} style={{ minWidth:280 }}><option value="">Choose a snapshot…</option>{marks.map(m=>(<option key={m.at} value={m.at}>{m.label}</option>))}</select>
      <button onClick={load} disabled={!selected||loading}>Load</button>
      <button onClick={persist} disabled={!snapshot.length||busy}>Persist as new views</button>
      {error && <span style={{ color:"red" }}>{error}</span>}
    </div>
    {snapshot.length>0 && (<div style={{ border:"1px solid #333", borderRadius:8, padding:8 }}><MultiViewEditor layers={toLayers(snapshot)} onChangeLayer={()=>{}} onCommitNewView={()=>{}} onReorderLayers={()=>{}} /></div>)}
  </div>);
}