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
      const rows = data ?? [];
      setTicks(
        rows.map((row) => ({
          tick: row.tick,
          source: row.source ?? "",
          id: row.id,
        }))
      );
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
      const rows = data ?? [];
      return rows.map((row) => ({
        message_id: row.message_id,
        view_id: row.view_id,
        block_id: row.block_id,
        archetype: row.archetype,
        variant: row.variant,
        seed: row.seed,
        layout: row.layout,
        style: row.style,
        locked: row.locked,
        visible: row.visible,
        z: row.z,
        created_at: row.created_at,
      }));
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
