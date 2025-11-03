// WARNING: Simplified demo. For production, add auth checks and robust signing.
Deno.serve(async (req) => {
  try {
    const url = new URL(req.url);
    const kind = url.searchParams.get("k") || "playlist"; // playlist | segment
    const itemId = url.searchParams.get("itemId");
    const path = url.searchParams.get("path") || ""; // for segments
    const server = Deno.env.get("JELLYFIN_SERVER_URL") || "";
    const apiKey = Deno.env.get("JELLYFIN_API_KEY") || "";

    if (!itemId) return new Response("Missing itemId", { status: 400 });

    if (kind === "playlist") {
      // Example HLS path (adjust to your Jellyfin version)
      const upstream = `${server.replace(/\/$/, "")}/Videos/${itemId}/live.m3u8?api_key=${apiKey}`;
      const resp = await fetch(upstream);
      if (!resp.ok) return new Response("Upstream error", { status: 502 });
      const text = await resp.text();
      // Rewrite segment URIs to proxy through this function
      const base = url.origin + url.pathname;
      const rewritten = text.replace(/(.*\.ts)/g, (m) => `${base}?k=segment&itemId=${encodeURIComponent(itemId)}&path=${encodeURIComponent(m)}`);
      return new Response(rewritten, { headers: { "content-type": "application/vnd.apple.mpegurl" } });
    } else {
      // Passthrough for a single segment path (provided by playlist rewrite)
      const upstream = `${server.replace(/\/$/, "")}/${path.replace(/^\//,"")}${path.includes("api_key") ? "" : `?api_key=${apiKey}`}`;
      const resp = await fetch(upstream);
      if (!resp.ok) return new Response("Segment upstream error", { status: 502 });
      return new Response(resp.body, { headers: { "content-type": resp.headers.get("content-type") || "video/MP2T" } });
    }
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500 });
  }
});