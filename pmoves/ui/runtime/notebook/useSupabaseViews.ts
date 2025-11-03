"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

export type Message = { id: string; thread_id: string; text: string; cgp?: any; created_at: string };
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
      const messageRows = (msgData as Message[]) || [];
      setMessages(messageRows);

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
      (blockData as ContentBlock[] | null)?.forEach((block) => {
        (blockMap[block.message_id] ||= []).push(block);
      });
      setBlocks(blockMap);

      const { data: viewData } = await supabase
        .from("message_views")
        .select("*")
        .in("message_id", ids)
        .order("created_at", { ascending: true });

      const viewMap: Record<string, MessageView[]> = {};
      (viewData as MessageView[] | null)?.forEach((view) => {
        (viewMap[view.message_id] ||= []).push(view);
      });
      setViews(viewMap);
      setLoading(false);

      const channel = supabase.channel(`views:${threadId}`);
      channel.on("postgres_changes", { event: "*", schema: "public", table: "message_views" }, (payload) => {
        const next = payload.new as MessageView;
        const messageId = next.message_id;
        setViews((current) => {
          const list = (current[messageId] || []).slice();
          const index = list.findIndex((item) => item.id === next.id);
          if (payload.eventType === "INSERT") list.push(next);
          else if (payload.eventType === "UPDATE" && index >= 0) list[index] = next;
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
    const payload: Record<string, any> = {
      message_id: view.message_id,
      block_id: view.block_id,
      archetype: view.archetype,
      variant: view.variant || null,
      seed: view.seed || null,
      layout: view.layout || null,
      style: view.style || null,
      locked: view.locked ?? false,
      visible: view.visible ?? true,
      z: view.z ?? 0,
    };
    const { error: insertError } = await supabase.from("message_views").insert(payload);
    if (insertError) throw insertError;
  }

  return { messages, blocks, views, latestViewOf, saveNewView, loading, error };
}
