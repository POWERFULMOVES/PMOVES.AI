import React from "react";
type Props = { selection:string[]; onAlign:(m:'left'|'center'|'right'|'top'|'middle'|'bottom')=>void; onDistribute:(a:'h'|'v')=>void; onEqualize:(w:'w'|'h'|'both')=>void; onReorder:(op:'front'|'back'|'up'|'down')=>void; onGroup:()=>void; onUngroup:()=>void; onSaveSelection:()=>void; onLock:(v:boolean)=>void; onVisible:(v:boolean)=>void; smartSnap:boolean; setSmartSnap:(v:boolean)=>void; baseline:boolean; setBaseline:(v:boolean)=>void; };
export function CanvasToolbar({ selection, onAlign, onDistribute, onEqualize, onReorder, onGroup, onUngroup, onSaveSelection, onLock, onVisible, smartSnap, setSmartSnap, baseline, setBaseline }:Props){
  const disabled = selection.length===0; const multi = selection.length>1;
  return (<div style={{ display:"flex", gap:8, flexWrap:"wrap", border:"1px solid #333", borderRadius:8, padding:8, background:"#0f1115" }}>
    <span style={{ opacity:0.75 }}>Selection: {selection.length||0}</span>
    <div style={{ borderLeft:"1px solid #333", marginLeft:8, paddingLeft:8, display:"flex", gap:8 }}>
      <button disabled={!multi} onClick={()=>onAlign('left')}>Align Left</button>
      <button disabled={!multi} onClick={()=>onAlign('center')}>Align Center</button>
      <button disabled={!multi} onClick={()=>onAlign('right')}>Align Right</button>
      <button disabled={!multi} onClick={()=>onAlign('top')}>Align Top</button>
      <button disabled={!multi} onClick={()=>onAlign('middle')}>Align Middle</button>
      <button disabled={!multi} onClick={()=>onAlign('bottom')}>Align Bottom</button>
    </div>
    <div style={{ borderLeft:"1px solid #333", marginLeft:8, paddingLeft:8, display:"flex", gap:8 }}>
      <button disabled={!multi} onClick={()=>onDistribute('h')}>Distribute H</button>
      <button disabled={!multi} onClick={()=>onDistribute('v')}>Distribute V</button>
      <button disabled={!multi} onClick={()=>onEqualize('w')}>Equalize W</button>
      <button disabled={!multi} onClick={()=>onEqualize('h')}>Equalize H</button>
      <button disabled={!multi} onClick={()=>onEqualize('both')}>Equalize Both</button>
    </div>
    <div style={{ borderLeft:"1px solid #333", marginLeft:8, paddingLeft:8, display:"flex", gap:8 }}>
      <button disabled={disabled} onClick={()=>onReorder('front')}>Bring to Front</button>
      <button disabled={disabled} onClick={()=>onReorder('up')}>Bring Forward</button>
      <button disabled={disabled} onClick={()=>onReorder('down')}>Send Backward</button>
      <button disabled={disabled} onClick={()=>onReorder('back')}>Send to Back</button>
    </div>
    <div style={{ borderLeft:"1px solid #333", marginLeft:8, paddingLeft:8, display:"flex", gap:8 }}>
      <button disabled={!multi} onClick={onGroup}>Group</button>
      <button disabled={!multi} onClick={onUngroup}>Ungroup</button>
    </div>
    <div style={{ borderLeft:"1px solid #333", marginLeft:8, paddingLeft:8, display:"flex", gap:8, alignItems:"center" }}>
      <label><input type="checkbox" checked={smartSnap} onChange={e=>setSmartSnap(e.target.checked)}/> Smart Snap</label>
      <label><input type="checkbox" checked={baseline} onChange={e=>setBaseline(e.target.checked)}/> Baseline</label>
      <button disabled={disabled} onClick={()=>onLock(true)}>Lock</button>
      <button disabled={disabled} onClick={()=>onLock(false)}>Unlock</button>
      <button disabled={disabled} onClick={()=>onVisible(true)}>Show</button>
      <button disabled={disabled} onClick={()=>onVisible(false)}>Hide</button>
      <button disabled={disabled} onClick={onSaveSelection}>Save Selection</button>
    </div>
  </div>);
}