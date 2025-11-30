import React, { useState } from "react";
import { SkinProvider } from "@/runtime/skin/SkinProvider";
import { useSupabaseViews } from "@/runtime/notebook/useSupabaseViews";
import { ViewEditor } from "@/runtime/notebook/ViewEditor"; // not included: leave as future
export default function NotebookDemo(){
  const [threadId,setThreadId]=useState(""); const { messages,blocks,views,latestViewOf,saveNewView } = useSupabaseViews(threadId);
  const first=messages[0]; const history=first?(views[first.id]||[]):[]; const block=first?(blocks[first.id]?.[0]):undefined;
  const view= first&&block ? (latestViewOf(first.id) || { message_id:first.id, block_id:block.id, archetype:"speech.round", variant:"primary", seed:42, layout:{ x:100,y:100,w:320,h:200 } }) : undefined;
  return (<SkinProvider url="/skins/comic-pop/1.1.0/skin.json"><div style={{ padding:20 }}><h1>Notebook Demo</h1><label>Thread ID <input value={threadId} onChange={e=>setThreadId(e.target.value)} /></label>{!threadId? <p>Enter thread id.</p> : null}{view && <div>/* ViewEditor omitted in v10 quick demo */</div>}</div></SkinProvider>);
}