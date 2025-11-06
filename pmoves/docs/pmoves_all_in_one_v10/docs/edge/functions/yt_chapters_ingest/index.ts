import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
function parseChapters(desc){
  const lines = desc.split(/\r?\n/); const out=[];
  for (const ln of lines){
    const m = ln.match(/(\d{1,2}:)?\d{1,2}:\d{2}/); if (!m) continue;
    const parts = m[0].split(":").map(n=>parseInt(n,10));
    const secs = parts.length===3 ? parts[0]*3600+parts[1]*60+parts[2] : parts[0]*60+parts[1];
    const title = ln.replace(m[0],"").trim().replace(/^[-–—:\s]+/,"") || `Chapter ${out.length+1}`;
    out.push({ t: secs, title });
  } return out;
}
Deno.serve(async (req)=>{
  try {
    const url = new URL(req.url);
    const videoId = url.searchParams.get("videoId");
    const messageId = url.searchParams.get("messageId");
    if (!videoId) return new Response("Missing videoId", { status: 400 });
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const apiKey = Deno.env.get("YOUTUBE_API_KEY")!;
    const resp = await fetch(`https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${videoId}&key=${apiKey}`);
    if (!resp.ok) return new Response("YouTube API error", { status: 502 });
    const json = await resp.json();
    const desc = json.items?.[0]?.snippet?.description || "";
    const chapters = parseChapters(desc);
    let blockId = null;
    if (messageId) {
      const { data } = await supabase.from("content_blocks").select("id,meta").eq("message_id",messageId).eq("kind","video").limit(1);
      blockId = data?.[0]?.id || null;
    }
    if (!blockId) {
      const { data } = await supabase.from("content_blocks").select("id,meta").contains("meta", { provider:"youtube", videoId }).limit(1);
      blockId = data?.[0]?.id || null;
    }
    if (!blockId) return new Response("video block not found", { status: 404 });
    const { data: cur } = await supabase.from("content_blocks").select("meta").eq("id", blockId).single();
    const meta = { ...(cur?.meta||{}), chapters };
    const { error } = await supabase.from("content_blocks").update({ meta }).eq("id", blockId);
    if (error) throw error;
    return new Response(JSON.stringify({ ok:true, chapters }), { headers: { "content-type":"application/json" } });
  } catch(e){ return new Response(JSON.stringify({ error:String(e) }), { status: 500 }); }
});