"use client";

import React, { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase";
import type { Database } from "@/lib/database.types";

type SnapshotBookmark = {
  id: string;
  name: string;
  at: string;
  tags?: string[] | null;
  position?: number | null;
};

type SnapshotRow = Pick<Database["public"]["Tables"]["snapshots"]["Row"], "id" | "name" | "at" | "tags" | "position">;

export function SnapshotBookmarksPro({ threadId, onPick }: { threadId: string; onPick: (iso: string) => void }) {
  const [items, setItems] = useState<SnapshotBookmark[]>([]);
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [dragId, setDragId] = useState<string | undefined>();

  const load = useCallback(async () => {
    if (!threadId) return;
    const { data } = await supabase
      .from("snapshots")
      .select("id,name,at,tags,position")
      .eq("thread_id", threadId)
      .order("position", { ascending: true })
      .order("created_at", { ascending: false });
    startTransition(() => {
      const rows = (data as SnapshotRow[] | null) ?? [];
      setItems(
        rows.map((row) => ({
          id: row.id,
          name: row.name ?? "",
          at: row.at,
          tags: row.tags ?? null,
          position: row.position ?? null,
        }))
      );
    });
  }, [threadId]);

  useEffect(() => {
    if (threadId) load();
  }, [load, threadId]);

  async function add() {
    if (!name) return;
    const tagList = tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    const position = (items[items.length - 1]?.position || 0) + 1;
    const { error } = await supabase.from("snapshots").insert({
      thread_id: threadId,
      name,
      at: new Date().toISOString(),
      tags: tagList,
      position,
    });
    if (!error) {
      setName("");
      setTags("");
      await load();
    }
  }

  async function swap(a: SnapshotBookmark, b: SnapshotBookmark) {
    await supabase.from("snapshots").update({ position: b.position }).eq("id", a.id);
    await supabase.from("snapshots").update({ position: a.position }).eq("id", b.id);
    await load();
  }

  function onDragStart(event: React.DragEvent, id: string) {
    setDragId(id);
    event.dataTransfer.effectAllowed = "move";
  }

  function onDragOver(event: React.DragEvent) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  async function onDrop(event: React.DragEvent, id: string) {
    event.preventDefault();
    if (!dragId || dragId === id) return;
    const from = items.find((item) => item.id === dragId);
    const to = items.find((item) => item.id === id);
    if (from && to) await swap(from, to);
    setDragId(undefined);
  }

  const filtered = useMemo(() => {
    const needle = query.toLowerCase();
    return items.filter((snapshot) => {
      if (!needle) return true;
      const inName = snapshot.name.toLowerCase().includes(needle);
      const inTags = (snapshot.tags || []).some((tag) => tag.toLowerCase().includes(needle));
      return inName || inTags;
    });
  }, [items, query]);

  return (
    <div style={{ border: "1px solid #333", borderRadius: 8, padding: 12, display: "grid", gap: 8 }}>
      <h3 style={{ margin: 0 }}>Snapshot Bookmarks (Pro)</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <input placeholder="Search name or tag…" value={query} onChange={(event) => setQuery(event.target.value)} />
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="New snapshot name" value={name} onChange={(event) => setName(event.target.value)} />
          <input placeholder="tags (comma)" value={tags} onChange={(event) => setTags(event.target.value)} />
          <button onClick={add}>Add</button>
        </div>
      </div>
      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: 0,
          display: "flex",
          flexDirection: "column",
          gap: 6,
          maxHeight: 240,
          overflowY: "auto",
        }}
      >
        {filtered.map((snapshot) => (
          <li
            key={snapshot.id}
            draggable
            onDragStart={(event) => onDragStart(event, snapshot.id)}
            onDragOver={onDragOver}
            onDrop={(event) => onDrop(event, snapshot.id)}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto",
              gap: 8,
              alignItems: "center",
              border: dragId === snapshot.id ? "1px dashed #ffd400" : "1px solid #333",
              borderRadius: 6,
              padding: 6,
            }}
          >
            <button onClick={() => onPick(snapshot.at)} style={{ textAlign: "left" }}>
              {snapshot.name}
              <span style={{ opacity: 0.6, fontSize: 12 }}>
                ({new Date(snapshot.at).toLocaleString()})
              </span>
              {(snapshot.tags || []).length ? (
                <span style={{ marginLeft: 8, opacity: 0.7 }}>
                  {(snapshot.tags || []).map((tag) => `#${tag}`).join(" ")}
                </span>
              ) : null}
            </button>
            <small style={{ opacity: 0.6 }}>pos {snapshot.position ?? "—"}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}
