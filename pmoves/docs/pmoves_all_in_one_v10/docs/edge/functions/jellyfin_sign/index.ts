import { encode as b64 } from "https://deno.land/std@0.203.0/encoding/base64.ts";
Deno.serve(async (req) => {
  try {
    const url = new URL(req.url);
    const itemId = url.searchParams.get("itemId");
    if (!itemId) return new Response("Missing itemId", { status: 400 });
    const ttlSec = Number(Deno.env.get("JELLYFIN_TTL_SEC") || "900");
    const expires = Math.floor(Date.now()/1000) + ttlSec;
    const payload = JSON.stringify({ itemId, exp: expires });
    const token = b64(payload);
    return new Response(JSON.stringify({ token, expires_at: new Date(expires*1000).toISOString() }), { headers: { "content-type":"application/json" } });
  } catch (e) { return new Response(JSON.stringify({ error: String(e) }), { status: 500 }); }
});