import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
type Skin = any;
const SkinCtx = createContext<{ skin?: Skin }|null>(null);
export const useSkin = () => useContext(SkinCtx)!;
export function SkinProvider({ url, children }:{ url:string; children:React.ReactNode }){
  const [skin, setSkin] = useState<Skin>();
  useEffect(()=>{ let alive = true; (async()=>{ const r = await fetch(url); const s = await r.json(); if(!alive) return; setSkin(s); const root = document.documentElement; const apply=(o:any)=>Object.entries(o).forEach(([k,v]:any)=>{ if(v&&typeof v==="object"&&!k.startsWith("--")) apply(v); else if (k.startsWith("--")) root.style.setProperty(k,String(v)); }); s.tokens&&apply(s.tokens); })(); return ()=>{ alive=false }; },[url]);
  const value = useMemo(()=>({ skin }),[skin]);
  return <SkinCtx.Provider value={value}>{children}</SkinCtx.Provider>;
}