import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
Deno.serve(async (req) => {
  try {
    const url = new URL(req.url);
    const videoId = url.searchParams.get("videoId");
    if (!videoId) return new Response("Missing videoId", { status: 400 });
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const ttlSec = Number(Deno.env.get("OEMBED_TTL_SEC") || "21600");
    const { data: rows } = await supabase.from("oembed_cache").select("*").eq("provider","youtube").eq("key",videoId).limit(1);
    if (rows && rows.length) {
      const row = rows[0];
      const freshUntil = new Date(row.fetched_at); freshUntil.setSeconds(freshUntil.getSeconds()+ttlSec);
      if (new Date() < freshUntil) return new Response(JSON.stringify(row.data), { headers: { "content-type":"application/json" } });
    }
    const oembedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(`https://www.youtube.com/watch?v=${videoId}`)}&format=json`;
    const r = await fetch(oembedUrl); if (!r.ok) return new Response("oEmbed fetch failed", { status: 502 });
    const data = await r.json();
    await supabase.from("oembed_cache").upsert({ provider:"youtube", key:videoId, data, fetched_at:new Date().toISOString() }, { onConflict:"provider,key" });
    return new Response(JSON.stringify(data), { headers: { "content-type":"application/json" } });
  } catch(e){ return new Response(JSON.stringify({ error: String(e) }), { status: 500 }); }
});