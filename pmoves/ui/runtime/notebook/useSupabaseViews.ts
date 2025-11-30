"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import type { Database } from "@/lib/database.types";

export type Message = { id: string; thread_id: string | null; text: string; cgp?: any; created_at: string };
export type ContentBlock = { id: string; message_id: string; kind: string; uri: string; meta?: any };
export type MessageView = {
  id?: string;
  message_id: string;
  block_id: string;
  archetype: string;
  variant?: string;
  seed?: number;
  layout?: any;
  style?: any;
  locked?: boolean;
  visible?: boolean;
  z?: number;
  created_by?: string;
  created_at?: string;
};

type UseSupabaseViewsResult = {
  messages: Message[];
  blocks: Record<string, ContentBlock[]>;
  views: Record<string, MessageView[]>;
  latestViewOf: (messageId: string) => MessageView | undefined;
  saveNewView: (view: MessageView) => Promise<void>;
  loading: boolean;
  error: string | null;
};

type MessageRow = Database["public"]["Tables"]["chat_messages"]["Row"];
type ContentBlockRow = Database["public"]["Tables"]["content_blocks"]["Row"];
type MessageViewRow = Database["public"]["Tables"]["message_views"]["Row"];
type MessageViewInsert = Database["public"]["Tables"]["message_views"]["Insert"];

const toMessage = (row: MessageRow): Message => ({
  id: row.id,
  thread_id: row.thread_id,
  text: row.text ?? "",
  cgp: row.cgp,
  created_at: row.created_at,
});

const toContentBlock = (row: ContentBlockRow): ContentBlock => ({
  id: row.id,
  message_id: row.message_id,
  kind: row.kind,
  uri: row.uri ?? "",
  meta: row.meta,
});

const toMessageView = (row: MessageViewRow): MessageView => ({
  id: row.id,
  message_id: row.message_id,
  block_id: row.block_id,
  archetype: row.archetype,
  variant: row.variant ?? undefined,
  seed: row.seed ?? undefined,
  layout: row.layout ?? undefined,
  style: row.style ?? undefined,
  locked: row.locked ?? undefined,
  visible: row.visible ?? undefined,
  z: row.z ?? undefined,
  created_by: row.created_by ?? undefined,
  created_at: row.created_at ?? undefined,
});

export function useSupabaseViews(threadId: string): UseSupabaseViewsResult {
  const [messages, setMessages] = useState<Message[]>([]);
  const [blocks, setBlocks] = useState<Record<string, ContentBlock[]>>({});
  const [views, setViews] = useState<Record<string, MessageView[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!threadId) return;
      setLoading(true);
      const { data: msgData, error: msgError } = await supabase
        .from("chat_messages")
        .select("id,thread_id,text,cgp,created_at")
        .eq("thread_id", threadId)
        .order("created_at", { ascending: true });
      if (msgError) {
        if (alive) setError(msgError.message);
        return;
      }
      const messageRows = (msgData as MessageRow[] | null) ?? [];
      setMessages(messageRows.map(toMessage));

      const ids = messageRows.map((message) => message.id);
      if (ids.length === 0) {
        setBlocks({});
        setViews({});
        setLoading(false);
        return;
      }

      const { data: blockData } = await supabase
        .from("content_blocks")
        .select("*")
        .in("message_id", ids);

      const blockMap: Record<string, ContentBlock[]> = {};
      (blockData as ContentBlockRow[] | null)?.forEach((block) => {
        const mapped = toContentBlock(block);
        (blockMap[mapped.message_id] ||= []).push(mapped);
      });
      setBlocks(blockMap);

      const { data: viewData } = await supabase
        .from("message_views")
        .select("*")
        .in("message_id", ids)
        .order("created_at", { ascending: true });

      const viewMap: Record<string, MessageView[]> = {};
      (viewData as MessageViewRow[] | null)?.forEach((view) => {
        const mapped = toMessageView(view);
        (viewMap[mapped.message_id] ||= []).push(mapped);
      });
      setViews(viewMap);
      setLoading(false);

      const channel = supabase.channel(`views:${threadId}`);
      channel.on("postgres_changes", { event: "*", schema: "public", table: "message_views" }, (payload) => {
        const next = payload.new as MessageViewRow | null;
        const messageId = next?.message_id;
        setViews((current) => {
          if (!messageId) return current;
          const list = (current[messageId] || []).slice();
          const index = next ? list.findIndex((item) => item.id === next.id) : -1;
          if (payload.eventType === "INSERT" && next) list.push(toMessageView(next));
          else if (payload.eventType === "UPDATE" && next && index >= 0) list[index] = toMessageView(next);
          return { ...current, [messageId]: list };
        });
      });
      channel.subscribe();
      return () => {
        channel.unsubscribe();
      };
    })();
    return () => {
      alive = false;
    };
  }, [threadId]);

  const latestViewOf = (messageId: string) => {
    const list = views[messageId] || [];
    return list.length ? list[list.length - 1] : undefined;
  };

  async function saveNewView(view: MessageView) {
    const payload: MessageViewInsert = {
      message_id: view.message_id,
      block_id: view.block_id,
      archetype: view.archetype,
      variant: view.variant ?? null,
      seed: view.seed ?? null,
      layout: view.layout ?? null,
      style: view.style ?? null,
      locked: view.locked ?? false,
      visible: view.visible ?? true,
      z: view.z ?? 0,
      created_by: view.created_by ?? null,
      created_at: view.created_at ?? null,
    };
    const { error: insertError } = await supabase.from("message_views").insert(payload);
    if (insertError) throw insertError;
  }

  return { messages, blocks, views, latestViewOf, saveNewView, loading, error };
}
