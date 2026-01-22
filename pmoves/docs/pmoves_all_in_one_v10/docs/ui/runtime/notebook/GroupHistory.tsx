import React from "react";
export function GroupHistory({ actions, onReplay }:{ actions:any[]; onReplay:(a:any)=>void; }){
  return (<div style={{ border:"1px solid #333", borderRadius:8, padding:12 }}><h3 style={{marginTop:0}}>Group Action Log</h3>
    <ol style={{listStyle:"none",padding:0,margin:0,display:"flex",flexDirection:"column",gap:8,maxHeight:240,overflowY:"auto"}}>
      {actions.map(a=>(<li key={a.id} style={{display:"flex",gap:8,alignItems:"center"}}><code style={{fontSize:12,minWidth:96}}>{a.action}</code><span style={{opacity:0.8}}>{JSON.stringify(a.params)}</span><button style={{marginLeft:"auto"}} onClick={()=>onReplay(a)}>Replay</button></li>))}
    </ol><small>Replaying applies stored params to current members.</small></div>);
}