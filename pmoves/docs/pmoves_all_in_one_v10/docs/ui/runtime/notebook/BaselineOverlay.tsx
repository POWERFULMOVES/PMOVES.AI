import React from "react";
export function BaselineOverlay({ baseline=20, color="#2a2d35", strongEvery=4 }:{ baseline?:number; color?:string; strongEvery?:number }){
  const rows = Array.from({ length: Math.ceil(480 / baseline) + 1 }, (_, i) => i);
  return (<div style={{ position:"absolute", inset:0, pointerEvents:"none" }}>{rows.map((i)=>(<div key={i} style={{ position:"absolute", left:0,right:0, top:i*baseline, height:0, borderTop:`1px solid ${i % strongEvery === 0 ? "#3a3f49" : color}` }}/>))}</div>);
}