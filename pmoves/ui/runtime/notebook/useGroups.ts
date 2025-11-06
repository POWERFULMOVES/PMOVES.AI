"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

export type ViewGroup = { id: string; thread_id: string; name: string; constraints?: any; created_at: string };
export type ViewGroupAction = {
  id: string;
  group_id: string;
  action: string;
  params: any;
  applied_to_message_ids: string[];
  created_at: string;
};

type UseGroupsResult = {
  groups: ViewGroup[];
  members: Record<string, string[]>;
  actions: Record<string, ViewGroupAction[]>;
  loading: boolean;
  error: string | null;
  createGroup: (name: string, constraints?: any) => Promise<ViewGroup | undefined>;
  renameGroup: (id: string, name: string) => Promise<void>;
  deleteGroup: (id: string) => Promise<void>;
  addMember: (groupId: string, messageId: string) => Promise<void>;
  removeMember: (groupId: string, messageId: string) => Promise<void>;
  logAction: (groupId: string, action: string, params: any, appliedTo: string[]) => Promise<void>;
};

export function useGroups(threadId: string): UseGroupsResult {
  const [groups, setGroups] = useState<ViewGroup[]>([]);
  const [members, setMembers] = useState<Record<string, string[]>>({});
  const [actions, setActions] = useState<Record<string, ViewGroupAction[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!threadId) return;
      setLoading(true);
      const { data: groupData, error: groupError } = await supabase
        .from("view_groups")
        .select("*")
        .eq("thread_id", threadId)
        .order("created_at", { ascending: true });
      if (groupError) {
        if (alive) setError(groupError.message);
        return;
      }
      const groupRows = (groupData as ViewGroup[]) || [];
      setGroups(groupRows);
      const groupIds = groupRows.map((group) => group.id);

      if (groupIds.length) {
        const { data: memberData } = await supabase
          .from("view_group_members")
          .select("group_id,message_id")
          .in("group_id", groupIds);
        const memberMap: Record<string, string[]> = {};
        (memberData as Array<{ group_id: string; message_id: string }> | null)?.forEach((row) => {
          (memberMap[row.group_id] ||= []).push(row.message_id);
        });
        setMembers(memberMap);

        const { data: actionData } = await supabase
          .from("view_group_actions")
          .select("*")
          .in("group_id", groupIds)
          .order("created_at", { ascending: true });

        const actionMap: Record<string, ViewGroupAction[]> = {};
        (actionData as ViewGroupAction[] | null)?.forEach((action) => {
          (actionMap[action.group_id] ||= []).push(action);
        });
        setActions(actionMap);
      }
      setLoading(false);

      const channel = supabase.channel(`groups:${threadId}`);
      channel.on("postgres_changes", { event: "*", schema: "public", table: "view_groups" }, (payload) => {
        const next = payload.new as ViewGroup;
        if (next?.thread_id !== threadId) return;
        setGroups((current) => {
          if (payload.eventType === "INSERT") return [...current, next];
          if (payload.eventType === "UPDATE") {
            return current.map((group) => (group.id === next.id ? next : group));
          }
          if (payload.eventType === "DELETE") {
            return current.filter((group) => group.id !== (payload.old as any)?.id);
          }
          return current;
        });
      });
      channel.on("postgres_changes", { event: "*", schema: "public", table: "view_group_members" }, (payload) => {
        const next = payload.new as { group_id: string; message_id: string };
        const groupId = next?.group_id || (payload.old as any)?.group_id;
        if (!groupId) return;
        setMembers((current) => {
          const set = new Set(current[groupId] || []);
          if (payload.eventType === "INSERT" && next?.message_id) set.add(next.message_id);
          if (payload.eventType === "DELETE" && (payload.old as any)?.message_id) {
            set.delete((payload.old as any).message_id);
          }
          return { ...current, [groupId]: Array.from(set) };
        });
      });
      channel.on("postgres_changes", { event: "*", schema: "public", table: "view_group_actions" }, (payload) => {
        const next = payload.new as ViewGroupAction;
        const groupId = next?.group_id || (payload.old as any)?.group_id;
        if (!groupId) return;
        setActions((current) => {
          const list = (current[groupId] || []).slice();
          if (payload.eventType === "INSERT") list.push(next);
          return { ...current, [groupId]: list };
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

  async function createGroup(name: string, constraints?: any) {
    const { data, error: insertError } = await supabase
      .from("view_groups")
      .insert({ thread_id: threadId, name, constraints: constraints || null })
      .select("*")
      .single();
    if (insertError) throw insertError;
    return data as ViewGroup;
  }

  async function renameGroup(id: string, name: string) {
    const { error: updateError } = await supabase.from("view_groups").update({ name }).eq("id", id);
    if (updateError) throw updateError;
  }

  async function deleteGroup(id: string) {
    const { error: deleteError } = await supabase.from("view_groups").delete().eq("id", id);
    if (deleteError) throw deleteError;
  }

  async function addMember(groupId: string, messageId: string) {
    const { error } = await supabase.from("view_group_members").insert({ group_id: groupId, message_id: messageId });
    if (error) throw error;
  }

  async function removeMember(groupId: string, messageId: string) {
    const { error } = await supabase
      .from("view_group_members")
      .delete()
      .match({ group_id: groupId, message_id: messageId });
    if (error) throw error;
  }

  async function logAction(groupId: string, action: string, params: any, appliedTo: string[]) {
    const { error } = await supabase
      .from("view_group_actions")
      .insert({ group_id: groupId, action, params, applied_to_message_ids: appliedTo });
    if (error) throw error;
  }

  return {
    groups,
    members,
    actions,
    loading,
    error,
    createGroup,
    renameGroup,
    deleteGroup,
    addMember,
    removeMember,
    logAction,
  };
}
