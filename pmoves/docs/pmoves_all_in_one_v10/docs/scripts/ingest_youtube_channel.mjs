import { createClient } from "@supabase/supabase-js"; import fetch from "node-fetch";
const { SUPABASE_URL, SUPABASE_ANON_KEY, THREAD_ID, USER_ID, YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID } = process.env;
if(!SUPABASE_URL||!SUPABASE_ANON_KEY||!THREAD_ID||!USER_ID||!YOUTUBE_API_KEY||!YOUTUBE_CHANNEL_ID){ console.error("Missing env"); process.exit(1); }
const supabase=createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
async function listVideos(){ const url=`https://www.googleapis.com/youtube/v3/search?key=${YOUTUBE_API_KEY}&channelId=${YOUTUBE_CHANNEL_ID}&part=snippet,id&order=date&maxResults=20`; const res=await fetch(url); if(!res.ok) throw new Error("yt search failed "+res.status); const json=await res.json(); return (json.items||[]).filter(x=>x.id?.videoId).map(x=>({ id:x.id.videoId,title:x.snippet.title,description:x.snippet.description })); }
async function ensureVideo(v){ const { data:found } = await supabase.from("chat_messages").select("id").eq("thread_id",THREAD_ID).contains("cgp",{ provider:"youtube", videoId:v.id }).limit(1); if(found&&found.length) return;
  const { data:msg, error:e1 } = await supabase.from("chat_messages").insert({ thread_id:THREAD_ID, author_id:USER_ID, role:"system", text:"YouTube: "+v.title, cgp:{ provider:"youtube", videoId:v.id } }).select("*").single(); if(e1) throw e1;
  const { data:blk, error:e2 } = await supabase.from("content_blocks").insert({ message_id:msg.id, kind:"video", uri:`yt://${v.id}`, meta:{ provider:"youtube", videoId:v.id } }).select("*").single(); if(e2) throw e2;
  await supabase.from("message_views").insert({ message_id:msg.id, block_id:blk.id, archetype:"digital.hud", variant:"primary", seed:42, layout:{ x:60,y:60,w:420,h:260 } });
  console.log("Inserted video", v.id);
}
(async()=>{ const vids=await listVideos(); for(const v of vids) await ensureVideo(v); console.log("Done."); })().catch(e=>{ console.error(e); process.exit(1); });