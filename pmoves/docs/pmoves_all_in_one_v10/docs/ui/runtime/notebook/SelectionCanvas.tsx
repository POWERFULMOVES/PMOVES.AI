import React, { useEffect, useRef, useState } from "react";
import { ComicBubble } from "@/runtime/skin/ComicBubble";
import type { MessageView } from "./useSupabaseViews";
type Layer = { id:string; view:MessageView; content?:React.ReactNode };
type Props = { layers:Layer[]; onChangeLayer?:(id:string,next:Partial<MessageView>)=>void; onCommitNewView?:(id:string)=>void; onSelectionChange?:(ids:string[])=>void; onReorderLayers?:(ids:string[])=>void; smartSnap?:boolean; baselinePx?:number; };
type Sel = { ids:Set<string> };
type Pt = { x:number;y:number };
function handleRect(x:number,y:number,w:number,h:number){ return { position:"absolute", left:x, top:y, width:w, height:h } as const; }
export function SelectionCanvas({ layers, onChangeLayer, onCommitNewView, onSelectionChange, onReorderLayers, smartSnap=true, baselinePx=20 }:Props){
  const [sel,setSel] = useState<Sel>({ ids:new Set() }); const [drag,setDrag] = useState<any>(null); const [guides,setGuides] = useState<any>({});
  useEffect(()=>{ function onKey(e:KeyboardEvent){ if(sel.ids.size===0) return; const d=e.shiftKey?10:1; if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key)) e.preventDefault(); if(e.key==="ArrowLeft") sel.ids.forEach(id=>nudge(id,-d,0)); if(e.key==="ArrowRight") sel.ids.forEach(id=>nudge(id,d,0)); if(e.key==="ArrowUp") sel.ids.forEach(id=>nudge(id,0,-d)); if(e.key==="ArrowDown") sel.ids.forEach(id=>nudge(id,0,d)); }
    function nudge(id:string,dx:number,dy:number){ const L=layers.find(l=>l.id===id); if(!L) return; const lay=L.view.layout||{}; onChangeLayer?.(id,{ layout:{ ...lay, x:(lay.x??0)+dx, y:(lay.y??0)+dy } as any }); }
    window.addEventListener("keydown",onKey); return ()=>window.removeEventListener("keydown",onKey);
  },[sel,layers,onChangeLayer]);
  function toggleSelect(id:string, add:boolean){ setSel(prev=>{ const ids=new Set(prev.ids); if(add){ ids.has(id)?ids.delete(id):ids.add(id); } else { ids.clear(); ids.add(id); } onSelectionChange?.(Array.from(ids)); return { ids }; }); }
  function computeSnap(x:number,y:number,w:number,h:number){ const threshold=6; const edges=layers.map(L=>{ const lay=L.view.layout||{}; const lx=lay.x??0, ly=lay.y??0, lw=lay.w??320, lh=lay.h??200; return { left:lx,right:lx+lw,cx:lx+lw/2,top:ly,bottom:ly+lh,cy:ly+lh/2 }; });
    let vGuide, hGuide, sx=x, sy=y; const cX=[{val:x},{val:x+w},{val:x+w/2}], cY=[{val:y},{val:y+h},{val:y+h/2}];
    for (const c of cX){ for (const e of edges){ for (const t of [e.left,e.right,e.cx]) if(Math.abs(c.val-t)<=threshold){ const d=t-c.val; sx+=d; vGuide=t; } } }
    for (const c of cY){ for (const e of edges){ for (const t of [e.top,e.bottom,e.cy]) if(Math.abs(c.val-t)<=threshold){ const d=t-c.val; sy+=d; hGuide=t; } } }
    if (baselinePx>0){ const near=Math.round(sy/baselinePx)*baselinePx; if(Math.abs(near-sy)<=threshold){ sy=near; hGuide=near; } } return { x:sx,y:sy,vGuide,hGuide };
  }
  function onMouseDownLayer(e:React.MouseEvent,id:string){ const L=layers.find(l=>l.id===id)!; const lay=L.view.layout||{}; const locked=(L.view as any).locked===true; if(locked) return;
    toggleSelect(id,e.shiftKey||e.metaKey); const start={ x:e.clientX,y:e.clientY }; setDrag({ id, start, orig:{ x:lay.x??0,y:lay.y??0,w:lay.w??320,h:lay.h??200 }, mode:"move" });
    (e.currentTarget as any).ownerDocument.addEventListener("mousemove",onMouseMove); (e.currentTarget as any).ownerDocument.addEventListener("mouseup",onMouseUp);
  }
  function onMouseDownHandle(e:React.MouseEvent,id:string,handle:string){ e.stopPropagation(); const L=layers.find(l=>l.id===id)!; const lay=L.view.layout||{}; const locked=(L.view as any).locked===true; if(locked) return;
    const start={ x:e.clientX,y:e.clientY }; setDrag({ id, start, orig:{ x:lay.x??0,y:lay.y??0,w:lay.w??320,h:lay.h??200 }, mode:"resize", handle });
    (e.currentTarget as any).ownerDocument.addEventListener("mousemove",onMouseMove); (e.currentTarget as any).ownerDocument.addEventListener("mouseup",onMouseUp);
  }
  function onMouseMove(e:MouseEvent){ if(!drag) return; const dx=e.clientX-drag.start.x, dy=e.clientY-drag.start.y;
    if(drag.mode==="move"){ const cur=smartSnap?computeSnap(drag.orig.x+dx,drag.orig.y+dy,drag.orig.w,drag.orig.h):{ x:drag.orig.x+dx,y:drag.orig.y+dy }; setGuides({ v:cur.vGuide,h:cur.hGuide }); sel.ids.forEach(id=>{ const L=layers.find(l=>l.id===id); if(!L) return; const lay=L.view.layout||{}; onChangeLayer?.(id,{ layout:{ ...lay, x:cur.x,y:cur.y } as any }); }); return; }
    if(drag.mode==="resize"){ const o=drag.orig; let x=o.x,y=o.y,w=o.w,h=o.h; const hdl=drag.handle!; if(hdl.includes("r")) w=Math.max(0,o.w+dx); if(hdl.includes("l")){ w=Math.max(0,o.w-dx); x=o.x+dx; } if(hdl.includes("b")) h=Math.max(0,o.h+dy); if(hdl.includes("t")){ h=Math.max(0,o.h-dy); y=o.y+dy; }
      const cur=smartSnap?computeSnap(x,y,w,h):{ x,y }; setGuides({ v:cur.vGuide,h:cur.hGuide }); onChangeLayer?.(drag.id,{ layout:{ ...(layers.find(l=>l.id===drag.id)!.view.layout||{}), x:cur.x,y:cur.y,w,h } as any });
    }
  }
  function onMouseUp(e:MouseEvent){ (e.target as any).ownerDocument.removeEventListener("mousemove",onMouseMove); (e.target as any).ownerDocument.removeEventListener("mouseup",onMouseUp); if(drag){ if(drag.mode==='move') sel.ids.forEach(id=>onCommitNewView?.(id)); else onCommitNewView?.(drag.id); } setGuides({}); setDrag(null); }
  function renderHandles(id:string,x:number,y:number,w:number,h:number){ const s=8; const hs=[["tl",x-s/2,y-s/2,"nwse-resize"],["tr",x+w-s/2,y-s/2,"nesw-resize"],["bl",x-s/2,y+h-s/2,"nesw-resize"],["br",x+w-s/2,y+h-s/2,"nwse-resize"],["l",x-s/2,y+h/2-s/2,"ew-resize"],["r",x+w-s/2,y+h/2-s/2,"ew-resize"],["t",x+w/2-s/2,y-s/2,"ns-resize"],["b",x+w/2-s/2,y+h-s/2,"ns-resize"]] as any[]; return hs.map(([k,l,t,c])=>(<div key={k} onMouseDown={(e)=>onMouseDownHandle(e,id,k)} style={{ position:"absolute", left:l, top:t, width:s,height:s, background:"#ffd400", border:"1px solid #121212", cursor:c }} />)); }
  return (<div className="pmoves-canvas" style={{ position:"relative", width:"100%", height:480, background:"#0b0b10", border:"1px dashed #333", borderRadius:8 }}>
    {guides.v!==undefined && (<div style={{ position:"absolute", left:guides.v, top:0, bottom:0, width:1, background:"#ffd400" }} />)}
    {guides.h!==undefined && (<div style={{ position:"absolute", top:guides.h, left:0, right:0, height:1, background:"#ffd400" }} />)}
    {layers.map(L=>{ const lay=L.view.layout||{}; const x=lay.x??80, y=lay.y??80, w=lay.w??320, h=lay.h??200; const selected=sel.ids.has(L.id); const locked=(L.view as any).locked===true; const visible=(L.view as any).visible!==false; if(!visible) return null; return (
      <div key={L.id} onMouseDown={locked?undefined:(e)=>onMouseDownLayer(e,L.id)} style={{ ...handleRect(x,y,w,h), cursor:locked?"not-allowed":"move", opacity: locked?0.85:1 }}>
        <ComicBubble archetype={L.view.archetype} variant={L.view.variant||"primary"} seed={L.view.seed||42} className="w-full h-full">{L.content||<div style={{ textAlign:"center" }}>Content</div>}</ComicBubble>
        {selected && !locked && (<><div style={{ position:"absolute", inset:0, border:"2px solid #ffd400", pointerEvents:"none" }} />{renderHandles(L.id,x,y,w,h)}</>)}
        {locked && <div style={{ position:"absolute", top:4, right:4, background:"#0b0b10", border:"1px solid #333", borderRadius:4, padding:"2px 6px", fontSize:12 }}>🔒</div>}
      </div> ); })}
  </div>);
}