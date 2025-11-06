import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
export type SnapshotTick = { tick:string; source:string; id:string };
export type SnapshotView = { message_id:string; view_id:string|null; block_id:string|null; archetype:string|null; variant:string|null; seed:number|null; layout:any; style:any; locked:boolean|null; visible:boolean|null; z:number|null; created_at:string|null; };
export function useSnapshots(threadId:string){
  const [ticks,setTicks]=useState<SnapshotTick[]>([]); const [loading,setLoading]=useState(false); const [error,setError]=useState<string|null>(null);
  async function refreshTicks(limit=200){ setLoading(true); const { data, error } = await supabase.rpc('rpc_snapshot_ticks',{ p_thread_id:threadId, p_limit:limit }); if(error){ setError(error.message); setLoading(false); return; } setTicks(data||[]); setLoading(false); }
  async function fetchSnapshot(atISO:string){ const { data, error } = await supabase.rpc('rpc_snapshot_views',{ p_thread_id:threadId, p_at:atISO }); if(error) throw error; return (data||[]) as SnapshotView[]; }
  useEffect(()=>{ if(threadId) refreshTicks(); },[threadId]);
  return { ticks, refreshTicks, fetchSnapshot, loading, error };
}