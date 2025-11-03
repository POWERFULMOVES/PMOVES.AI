import React from "react";
export type MediaMeta = { provider:'youtube'|'jellyfin'|'http'; videoId?:string; start?:number; url?:string; jellyfin?:{ serverUrl:string; itemId:string; apiKey?:string; }; };
function ytSrc(id:string,start=0){ const p=new URLSearchParams(); if(start) p.set('start',String(start)); p.set('rel','0'); p.set('modestbranding','1'); p.set('playsinline','1'); return `https://www.youtube.com/embed/${id}?${p.toString()}`; }
function jfUrl(meta:MediaMeta){ if(meta.url) return meta.url; if(!meta.jellyfin) return ""; const { serverUrl, itemId, apiKey } = meta.jellyfin; return `${serverUrl.replace(/\/$/,'')}/Videos/${itemId}/stream?static=true${apiKey?`&api_key=${apiKey}`:''}`; }
export function MediaEmbed({ meta, className }:{ meta:MediaMeta; className?:string }){
  if(meta.provider==='youtube'&&meta.videoId){ return <iframe className={className} src={ytSrc(meta.videoId,meta.start||0)} title="YouTube" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowFullScreen style={{ width:"100%", height:"100%", border:0 }} />; }
  if(meta.provider==='jellyfin'){ const src=jfUrl(meta); return <video className={className} src={src} controls style={{ width:"100%", height:"100%" }} />; }
  if(meta.provider==='http'&&meta.url){ return <video className={className} src={meta.url} controls style={{ width:"100%", height:"100%" }} />; }
  return <div style={{ display:"grid", placeItems:"center", width:"100%", height:"100%", color:"#888" }}>Unsupported media</div>;
}