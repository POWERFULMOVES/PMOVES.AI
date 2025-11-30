import {
  createClient,
  SupabaseClient,
  RealtimeChannel,
  RealtimePresenceState,
} from '@supabase/supabase-js';

export type CursorPosition = {
  x: number;
  y: number;
};

export type PresencePayload = {
  agent_id: string;
  board_id: string;
  session_id?: string;
  cursor?: CursorPosition | null;
  last_seen_at?: string;
  meta?: Record<string, any> | null;
};

export type PresenceSnapshot = {
  presenceKey: string;
  agentId: string;
  sessionId?: string;
  cursor: CursorPosition | null;
  lastSeenAt: string;
  meta: Record<string, any>;
};

export type PresenceStateMap = Record<string, PresenceSnapshot>;

export type PresenceSubscriptionOptions = {
  boardId: string;
  presenceKey: string;
  initialPayload?: Partial<PresencePayload>;
  onStateChange?: (state: PresenceStateMap) => void;
};

export type PresenceSubscription = {
  channel: RealtimeChannel;
  updatePresence: (payload: Partial<PresencePayload>) => Promise<void>;
  untrack: () => Promise<void>;
  unsubscribe: () => Promise<void>;
};

export type MessageRecord = {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  tokens?: number | null;
  meta: Record<string, any> | null;
  created_at: string;
};

export type MessageSubscriptionHandlers = {
  onInsert?: (message: MessageRecord) => void;
  onUpdate?: (message: MessageRecord) => void;
  onDelete?: (message: MessageRecord) => void;
};

export type SupabaseRealtimeConfig = {
  supabaseUrl?: string;
  anonKey?: string;
  serviceRoleKey?: string;
};

let cachedAnonClient: SupabaseClient | null = null;
let cachedServiceClientKey: string | null = null;
let cachedServiceClient: SupabaseClient | null = null;

function resolveConfig(config?: SupabaseRealtimeConfig) {
  const url =
    config?.supabaseUrl ??
    process.env.NEXT_PUBLIC_SUPABASE_URL ??
    process.env.SUPABASE_URL;
  const anonKey =
    config?.anonKey ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
    process.env.SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error(
      'Supabase Realtime configuration missing. Provide supabaseUrl and anonKey via options or environment variables.'
    );
  }

  return { url, anonKey, serviceRoleKey: config?.serviceRoleKey };
}

export function getSupabaseRealtimeClient(
  config?: SupabaseRealtimeConfig
): SupabaseClient {
  const { url, anonKey } = resolveConfig(config);
  if (cachedAnonClient) {
    return cachedAnonClient;
  }

  cachedAnonClient = createClient(url, anonKey, {
    realtime: {
      params: {
        eventsPerSecond: 5,
      },
    },
    global: {
      headers: {
        'x-client-info': 'pmoves-ui-realtime',
      },
    },
  });

  return cachedAnonClient;
}

export function getServiceRoleClient(
  config?: SupabaseRealtimeConfig
): SupabaseClient | null {
  const { url, serviceRoleKey } = resolveConfig(config);
  if (!serviceRoleKey) {
    return null;
  }

  if (cachedServiceClient && cachedServiceClientKey === serviceRoleKey) {
    return cachedServiceClient;
  }

  cachedServiceClient = createClient(url, serviceRoleKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
    global: {
      headers: {
        'x-client-info': 'pmoves-ui-realtime-service',
      },
    },
  });
  cachedServiceClientKey = serviceRoleKey;

  return cachedServiceClient;
}

function normalisePresenceState(
  state: RealtimePresenceState<PresencePayload>
): PresenceStateMap {
  const result: PresenceStateMap = {};

  Object.entries(state).forEach(([presenceKey, entries]) => {
    if (!entries || entries.length === 0) {
      return;
    }

    const latest = entries.reduce<PresencePayload>((acc, entry) => {
      if (!acc) {
        return entry;
      }

      const accTimestamp = acc.last_seen_at
        ? Date.parse(acc.last_seen_at)
        : 0;
      const entryTimestamp = entry.last_seen_at
        ? Date.parse(entry.last_seen_at)
        : 0;

      if (entryTimestamp >= accTimestamp) {
        return entry;
      }

      return acc;
    }, entries[0]);

    const agentId = latest.agent_id ?? presenceKey;

    result[agentId] = {
      presenceKey,
      agentId,
      sessionId: latest.session_id,
      cursor: latest.cursor ?? null,
      lastSeenAt: latest.last_seen_at ?? new Date().toISOString(),
      meta: latest.meta ?? {},
    };
  });

  return result;
}

export function subscribeToBoardPresence(
  client: SupabaseClient,
  options: PresenceSubscriptionOptions
): PresenceSubscription {
  const { boardId, presenceKey } = options;
  const channelName = `studio_board_presence:${boardId}`;
  let currentPayload: PresencePayload = {
    agent_id: presenceKey,
    board_id: boardId,
    cursor: options.initialPayload?.cursor ?? null,
    session_id: options.initialPayload?.session_id,
    last_seen_at: new Date().toISOString(),
    meta: options.initialPayload?.meta ?? {},
  };

  const channel = client.channel(channelName, {
    config: {
      presence: {
        key: presenceKey,
      },
    },
  });

  const emitState = () => {
    const state = channel.presenceState<PresencePayload>();
    options.onStateChange?.(normalisePresenceState(state));
  };

  channel
    .on('presence', { event: 'sync' }, emitState)
    .on('presence', { event: 'join' }, emitState)
    .on('presence', { event: 'leave' }, emitState);

  channel.subscribe((status) => {
    if (status === 'SUBSCRIBED') {
      channel.track(currentPayload).catch((error) => {
        console.error('Failed to register presence', error);
      });
    }
  });

  return {
    channel,
    updatePresence: async (payload) => {
      currentPayload = {
        ...currentPayload,
        ...payload,
        board_id: boardId,
        agent_id: currentPayload.agent_id,
        last_seen_at: new Date().toISOString(),
      };
      await channel.track(currentPayload);
    },
    untrack: async () => {
      await channel.untrack();
    },
    unsubscribe: async () => {
      await client.removeChannel(channel);
    },
  };
}

export function subscribeToSessionMessages(
  client: SupabaseClient,
  sessionId: string,
  handlers: MessageSubscriptionHandlers
): RealtimeChannel {
  const channelName = `session_messages:${sessionId}`;
  const channel = client.channel(channelName);

  const filter = `session_id=eq.${sessionId}`;

  channel
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'pmoves_core',
        table: 'message',
        filter,
      },
      (payload) => {
        handlers.onInsert?.(payload.new as MessageRecord);
      }
    )
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'pmoves_core',
        table: 'message',
        filter,
      },
      (payload) => {
        handlers.onUpdate?.(payload.new as MessageRecord);
      }
    )
    .on(
      'postgres_changes',
      {
        event: 'DELETE',
        schema: 'pmoves_core',
        table: 'message',
        filter,
      },
      (payload) => {
        handlers.onDelete?.(payload.old as MessageRecord);
      }
    );

  try {
    channel.subscribe();
  } catch (error) {
    console.error('Failed to subscribe to session messages', error);
  }

  return channel;
}

export async function fetchSessionMessages(
  client: SupabaseClient,
  sessionId: string
): Promise<MessageRecord[]> {
  const { data, error } = await client
    .from('pmoves_core.message')
    .select('id, session_id, role, content, tokens, meta, created_at')
    .eq('session_id', sessionId)
    .order('created_at', { ascending: true });

  if (error) {
    throw error;
  }

  return (data ?? []) as MessageRecord[];
}

export async function insertSessionMessage(
  client: SupabaseClient,
  message: Omit<MessageRecord, 'id' | 'created_at'>
): Promise<MessageRecord> {
  const { data, error } = await client
    .from('pmoves_core.message')
    .insert(message)
    .select('id, session_id, role, content, tokens, meta, created_at')
    .single();

  if (error) {
    throw error;
  }

  return data as MessageRecord;
}
