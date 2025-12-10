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

// ============================================================================
// Chat Messages Realtime (Phase 9)
// ============================================================================

export type ChatMessage = {
  id: number;
  owner_id: string;
  role: 'user' | 'agent';
  agent: string | null;
  agent_id: string | null;
  avatar_url: string | null;
  content: string;
  message_type: 'text' | 'action' | 'system' | 'approval';
  session_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export type ChatMessageHandlers = {
  onInsert?: (message: ChatMessage) => void;
  onUpdate?: (message: ChatMessage) => void;
  onDelete?: (message: ChatMessage) => void;
};

export function subscribeToChatMessages(
  client: SupabaseClient,
  ownerId: string,
  handlers: ChatMessageHandlers,
  sessionId?: string
): RealtimeChannel {
  const channelName = sessionId
    ? `chat_messages:session:${sessionId}`
    : `chat_messages:owner:${ownerId}`;
  const channel = client.channel(channelName);

  const filter = sessionId
    ? `session_id=eq.${sessionId}`
    : `owner_id=eq.${ownerId}`;

  channel
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'chat_messages',
        filter,
      },
      (payload) => {
        handlers.onInsert?.(payload.new as ChatMessage);
      }
    )
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'chat_messages',
        filter,
      },
      (payload) => {
        handlers.onUpdate?.(payload.new as ChatMessage);
      }
    )
    .on(
      'postgres_changes',
      {
        event: 'DELETE',
        schema: 'public',
        table: 'chat_messages',
        filter,
      },
      (payload) => {
        handlers.onDelete?.(payload.old as ChatMessage);
      }
    );

  channel.subscribe((status) => {
    if (status === 'SUBSCRIBED') {
      console.log(`[Realtime] Subscribed to chat_messages: ${channelName}`);
    }
  });

  return channel;
}

export async function fetchChatMessages(
  client: SupabaseClient,
  ownerId: string,
  options?: { limit?: number; sessionId?: string }
): Promise<ChatMessage[]> {
  let query = client
    .from('chat_messages')
    .select('id, owner_id, role, agent, agent_id, avatar_url, content, message_type, session_id, metadata, created_at')
    .eq('owner_id', ownerId)
    .order('created_at', { ascending: true });

  if (options?.sessionId) {
    query = query.eq('session_id', options.sessionId);
  }

  if (options?.limit) {
    query = query.limit(options.limit);
  }

  const { data, error } = await query;

  if (error) {
    throw error;
  }

  return (data ?? []) as ChatMessage[];
}

export async function insertChatMessage(
  client: SupabaseClient,
  message: Pick<ChatMessage, 'owner_id' | 'role' | 'content'> & Partial<ChatMessage>
): Promise<ChatMessage> {
  const { data, error } = await client
    .from('chat_messages')
    .insert({
      owner_id: message.owner_id,
      role: message.role,
      content: message.content,
      agent: message.agent ?? null,
      agent_id: message.agent_id ?? null,
      avatar_url: message.avatar_url ?? null,
      message_type: message.message_type ?? 'text',
      session_id: message.session_id ?? null,
      metadata: message.metadata ?? null,
    })
    .select('id, owner_id, role, agent, agent_id, avatar_url, content, message_type, session_id, metadata, created_at')
    .single();

  if (error) {
    throw error;
  }

  return data as ChatMessage;
}

// ============================================================================
// Ingestion Queue Realtime (Phase 9)
// ============================================================================

export type IngestionSourceType =
  | 'youtube'
  | 'pdf'
  | 'url'
  | 'upload'
  | 'notebook'
  | 'discord'
  | 'telegram'
  | 'rss';

export type IngestionStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'processing'
  | 'completed'
  | 'failed';

export type IngestionQueueItem = {
  id: string;
  owner_id: string | null;
  source_type: IngestionSourceType;
  source_url: string | null;
  source_id: string | null;
  title: string | null;
  description: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  source_meta: Record<string, unknown>;
  status: IngestionStatus;
  priority: number;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  processor_id: string | null;
  processing_started_at: string | null;
  processed_at: string | null;
  error_message: string | null;
  retry_count: number;
  output_refs: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type IngestionQueueHandlers = {
  onInsert?: (item: IngestionQueueItem) => void;
  onUpdate?: (item: IngestionQueueItem) => void;
  onDelete?: (item: IngestionQueueItem) => void;
};

export function subscribeToIngestionQueue(
  client: SupabaseClient,
  handlers: IngestionQueueHandlers,
  statusFilter?: IngestionStatus
): RealtimeChannel {
  const channelName = statusFilter
    ? `ingestion_queue:status:${statusFilter}`
    : 'ingestion_queue:all';
  const channel = client.channel(channelName);

  const baseConfig = {
    schema: 'public',
    table: 'ingestion_queue',
  };

  const filterConfig = statusFilter
    ? { ...baseConfig, filter: `status=eq.${statusFilter}` }
    : baseConfig;

  channel
    .on(
      'postgres_changes',
      { event: 'INSERT', ...filterConfig },
      (payload) => {
        handlers.onInsert?.(payload.new as IngestionQueueItem);
      }
    )
    .on(
      'postgres_changes',
      { event: 'UPDATE', ...filterConfig },
      (payload) => {
        handlers.onUpdate?.(payload.new as IngestionQueueItem);
      }
    )
    .on(
      'postgres_changes',
      { event: 'DELETE', ...filterConfig },
      (payload) => {
        handlers.onDelete?.(payload.old as IngestionQueueItem);
      }
    );

  channel.subscribe((status) => {
    if (status === 'SUBSCRIBED') {
      console.log(`[Realtime] Subscribed to ingestion_queue: ${channelName}`);
    }
  });

  return channel;
}

export async function fetchIngestionQueue(
  client: SupabaseClient,
  options?: {
    status?: IngestionStatus;
    sourceType?: IngestionSourceType;
    limit?: number;
    offset?: number;
  }
): Promise<IngestionQueueItem[]> {
  let query = client
    .from('ingestion_queue')
    .select('*')
    .order('priority', { ascending: false })
    .order('created_at', { ascending: true });

  if (options?.status) {
    query = query.eq('status', options.status);
  }

  if (options?.sourceType) {
    query = query.eq('source_type', options.sourceType);
  }

  if (options?.limit) {
    query = query.limit(options.limit);
  }

  if (options?.offset) {
    query = query.range(options.offset, options.offset + (options.limit ?? 50) - 1);
  }

  const { data, error } = await query;

  if (error) {
    throw error;
  }

  return (data ?? []) as IngestionQueueItem[];
}

export async function approveIngestion(
  client: SupabaseClient,
  id: string,
  priority?: number
): Promise<IngestionQueueItem | null> {
  const { data, error } = await client.rpc('approve_ingestion', {
    p_id: id,
    p_priority: priority ?? null,
  });

  if (error) {
    throw error;
  }

  return data as IngestionQueueItem | null;
}

export async function rejectIngestion(
  client: SupabaseClient,
  id: string,
  reason?: string
): Promise<IngestionQueueItem | null> {
  const { data, error } = await client.rpc('reject_ingestion', {
    p_id: id,
    p_reason: reason ?? null,
  });

  if (error) {
    throw error;
  }

  return data as IngestionQueueItem | null;
}

export async function fetchIngestionStats(
  client: SupabaseClient
): Promise<Array<{ status: IngestionStatus; source_type: IngestionSourceType; count: number }>> {
  const { data, error } = await client.rpc('get_ingestion_stats');

  if (error) {
    throw error;
  }

  return (data ?? []) as Array<{ status: IngestionStatus; source_type: IngestionSourceType; count: number }>;
}
