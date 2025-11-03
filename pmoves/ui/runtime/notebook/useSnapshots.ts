"use client";

import { startTransition, useCallback, useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

export type SnapshotTick = { tick: string; source: string; id: string };
export type SnapshotView = {
  message_id: string;
  view_id: string | null;
  block_id: string | null;
  archetype: string | null;
  variant: string | null;
  seed: number | null;
  layout: any;
  style: any;
  locked: boolean | null;
  visible: boolean | null;
  z: number | null;
  created_at: string | null;
};

type UseSnapshotsResult = {
  ticks: SnapshotTick[];
  refreshTicks: (limit?: number) => Promise<void>;
  fetchSnapshot: (atISO: string) => Promise<SnapshotView[]>;
  loading: boolean;
  error: string | null;
};

export function useSnapshots(threadId: string): UseSnapshotsResult {
  const [ticks, setTicks] = useState<SnapshotTick[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshTicks = useCallback(
    async (limit = 200) => {
      if (!threadId) return;
      setLoading(true);
      const { data, error: rpcError } = await supabase.rpc("rpc_snapshot_ticks", {
        p_thread_id: threadId,
        p_limit: limit,
      });
      if (rpcError) {
        setError(rpcError.message);
        setLoading(false);
        return;
      }
      setTicks((data as SnapshotTick[]) || []);
      setLoading(false);
    },
    [threadId]
  );

  const fetchSnapshot = useCallback(
    async (atISO: string) => {
      if (!threadId) return [];
      const { data, error: rpcError } = await supabase.rpc("rpc_snapshot_views", {
        p_thread_id: threadId,
        p_at: atISO,
      });
      if (rpcError) throw rpcError;
      return (data as SnapshotView[]) || [];
    },
    [threadId]
  );

  useEffect(() => {
    if (!threadId) return;
    startTransition(() => {
      void refreshTicks();
    });
  }, [refreshTicks, threadId]);

  return { ticks, refreshTicks, fetchSnapshot, loading, error };
}
