"use client";

import React from "react";

export type MediaMeta = {
  provider: "youtube" | "jellyfin" | "http";
  videoId?: string;
  start?: number;
  url?: string;
  jellyfin?: { serverUrl: string; itemId: string; apiKey?: string };
};

const youtubeSrc = (id: string, start = 0) => {
  const params = new URLSearchParams();
  if (start) params.set("start", String(start));
  params.set("rel", "0");
  params.set("modestbranding", "1");
  params.set("playsinline", "1");
  return `https://www.youtube.com/embed/${id}?${params.toString()}`;
};

const jellyfinUrl = (meta: MediaMeta) => {
  if (meta.url) return meta.url;
  if (!meta.jellyfin) return "";
  const { serverUrl, itemId, apiKey } = meta.jellyfin;
  const base = serverUrl.replace(/\/$/, "");
  const suffix = apiKey ? `&api_key=${apiKey}` : "";
  return `${base}/Videos/${itemId}/stream?static=true${suffix}`;
};

export function MediaEmbed({ meta, className }: { meta: MediaMeta; className?: string }) {
  if (meta.provider === "youtube" && meta.videoId) {
    return (
      <iframe
        className={className}
        src={youtubeSrc(meta.videoId, meta.start || 0)}
        title="YouTube"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
        style={{ width: "100%", height: "100%", border: 0 }}
      />
    );
  }
  if (meta.provider === "jellyfin") {
    const src = jellyfinUrl(meta);
    return <video className={className} src={src} controls style={{ width: "100%", height: "100%" }} />;
  }
  if (meta.provider === "http" && meta.url) {
    return <video className={className} src={meta.url} controls style={{ width: "100%", height: "100%" }} />;
  }
  return (
    <div style={{ display: "grid", placeItems: "center", width: "100%", height: "100%", color: "#888" }}>
      Unsupported media
    </div>
  );
}
