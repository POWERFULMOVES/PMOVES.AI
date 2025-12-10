/**
 * @fileoverview Supabase Realtime Client for PMOVES UI
 *
 * Provides real-time subscriptions and data operations for:
 * - Board presence (cursor positions, agent activity)
 * - Session messages (agent/user conversations)
 * - Chat messages (Phase 9: agent chat relay)
 * - Ingestion queue (Phase 9: content approval workflow)
 *
 * @module realtimeClient
 */

import {
  createClient,
  SupabaseClient,
  RealtimeChannel,
  RealtimePresenceState,
} from '@supabase/supabase-js';

/**
 * Represents a cursor position on the studio board.
 */
export type CursorPosition = {
  /** X coordinate in pixels */
  x: number;
  /** Y coordinate in pixels */
  y: number;
};

/**
 * Payload sent when tracking presence on a board.
 */
export type PresencePayload = {
  /** Unique identifier for the agent */
  agent_id: string;
  /** Board being tracked */
  board_id: string;
  /** Optional session identifier */
  session_id?: string;
  /** Current cursor position, null if not tracking cursor */
  cursor?: CursorPosition | null;
  /** ISO timestamp of last activity */
  last_seen_at?: string;
  /** Additional metadata */
  meta?: Record<string, any> | null;
};

/**
 * Normalized snapshot of presence state for a single agent.
 */
export type PresenceSnapshot = {
  /** Unique key for this presence entry */
  presenceKey: string;
  /** Agent identifier */
  agentId: string;
  /** Associated session ID */
  sessionId?: string;
  /** Current cursor position */
  cursor: CursorPosition | null;
  /** ISO timestamp of last activity */
  lastSeenAt: string;
  /** Additional metadata */
  meta: Record<string, any>;
};

/**
 * Map of agent IDs to their presence snapshots.
 */
export type PresenceStateMap = Record<string, PresenceSnapshot>;

/**
 * Options for subscribing to board presence.
 */
export type PresenceSubscriptionOptions = {
  /** Board to subscribe to */
  boardId: string;
  /** Unique key for this client's presence */
  presenceKey: string;
  /** Initial payload to track */
  initialPayload?: Partial<PresencePayload>;
  /** Callback when presence state changes */
  onStateChange?: (state: PresenceStateMap) => void;
};

/**
 * Handle for managing a presence subscription.
 */
export type PresenceSubscription = {
  /** The underlying Realtime channel */
  channel: RealtimeChannel;
  /** Update this client's presence data */
  updatePresence: (payload: Partial<PresencePayload>) => Promise<void>;
  /** Stop tracking presence */
  untrack: () => Promise<void>;
  /** Unsubscribe from the channel */
  unsubscribe: () => Promise<void>;
};

/**
 * Record from the pmoves_core.message table.
 */
export type MessageRecord = {
  /** Unique message ID */
  id: string;
  /** Session this message belongs to */
  session_id: string;
  /** Message role */
  role: 'user' | 'assistant' | 'system' | 'tool';
  /** Message content */
  content: string;
  /** Token count for LLM tracking */
  tokens?: number | null;
  /** Additional metadata */
  meta: Record<string, any> | null;
  /** ISO timestamp of creation */
  created_at: string;
};

/**
 * Handlers for message subscription events.
 */
export type MessageSubscriptionHandlers = {
  /** Called when a new message is inserted */
  onInsert?: (message: MessageRecord) => void;
  /** Called when a message is updated */
  onUpdate?: (message: MessageRecord) => void;
  /** Called when a message is deleted */
  onDelete?: (message: MessageRecord) => void;
};

/**
 * Configuration for Supabase Realtime client.
 */
export type SupabaseRealtimeConfig = {
  /** Supabase project URL */
  supabaseUrl?: string;
  /** Anonymous key for client-side access */
  anonKey?: string;
  /** Service role key for server-side operations */
  serviceRoleKey?: string;
};

let cachedAnonClient: SupabaseClient | null = null;
let cachedServiceClientKey: string | null = null;
let cachedServiceClient: SupabaseClient | null = null;

/**
 * Resolves Supabase configuration from options or environment variables.
 *
 * @param config - Optional configuration overrides
 * @returns Resolved configuration with url, anonKey, and optional serviceRoleKey
 * @throws Error if supabaseUrl or anonKey cannot be resolved
 */
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

/**
 * Gets or creates a cached Supabase client for Realtime operations.
 *
 * Uses the anonymous key for client-side access. The client is cached
 * globally to ensure only one connection is maintained.
 *
 * @param config - Optional configuration overrides
 * @returns Supabase client configured for Realtime
 *
 * @example
 * ```typescript
 * const client = getSupabaseRealtimeClient();
 * const channel = client.channel('my-channel');
 * ```
 */
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

/**
 * Gets or creates a cached Supabase client with service role permissions.
 *
 * This client bypasses Row Level Security and should only be used
 * server-side. Returns null if no service role key is available.
 *
 * @param config - Configuration including serviceRoleKey
 * @returns Supabase client with service role, or null if unavailable
 */
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

/**
 * Normalizes raw Realtime presence state into a cleaner format.
 *
 * Takes the latest entry for each presence key based on last_seen_at
 * timestamp, handling cases where multiple entries exist for the same key.
 *
 * @param state - Raw presence state from Supabase Realtime
 * @returns Normalized map of agent IDs to presence snapshots
 */
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

/**
 * Subscribes to presence updates for a studio board.
 *
 * Tracks this client's presence and receives updates when other
 * agents join, leave, or update their cursor positions.
 *
 * @param client - Supabase client to use
 * @param options - Subscription options including boardId and callbacks
 * @returns Handle for managing the subscription
 *
 * @example
 * ```typescript
 * const sub = subscribeToBoardPresence(client, {
 *   boardId: 'board-123',
 *   presenceKey: 'agent-456',
 *   onStateChange: (state) => console.log('Presence:', state),
 * });
 *
 * // Update cursor position
 * await sub.updatePresence({ cursor: { x: 100, y: 200 } });
 *
 * // Cleanup
 * await sub.unsubscribe();
 * ```
 */
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

/**
 * Subscribes to message changes for a session in pmoves_core.message.
 *
 * @param client - Supabase client to use
 * @param sessionId - Session ID to filter messages
 * @param handlers - Callbacks for insert/update/delete events
 * @returns The Realtime channel for the subscription
 *
 * @example
 * ```typescript
 * const channel = subscribeToSessionMessages(client, 'session-123', {
 *   onInsert: (msg) => console.log('New message:', msg.content),
 * });
 *
 * // Cleanup
 * await client.removeChannel(channel);
 * ```
 */
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

/**
 * Fetches all messages for a session from pmoves_core.message.
 *
 * @param client - Supabase client to use
 * @param sessionId - Session ID to fetch messages for
 * @returns Array of messages ordered by creation time (ascending)
 * @throws Supabase error if the query fails
 */
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

/**
 * Inserts a new message into pmoves_core.message.
 *
 * @param client - Supabase client to use
 * @param message - Message data (id and created_at are auto-generated)
 * @returns The inserted message record
 * @throws Supabase error if the insert fails
 */
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

/**
 * Represents a chat message in the public.chat_messages table.
 *
 * Used for agent-user conversations relayed through the chat-relay service.
 */
export type ChatMessage = {
  /** Auto-incremented message ID */
  id: number;
  /** Owner (user) ID */
  owner_id: string;
  /** Message role: 'user' for user messages, 'agent' for agent responses */
  role: 'user' | 'agent';
  /** Agent name (for agent messages) */
  agent: string | null;
  /** Agent identifier (for agent messages) */
  agent_id: string | null;
  /** Agent avatar URL */
  avatar_url: string | null;
  /** Message content */
  content: string;
  /** Message type for UI rendering */
  message_type: 'text' | 'action' | 'system' | 'approval';
  /** Session ID for conversation grouping */
  session_id: string | null;
  /** Additional metadata */
  metadata: Record<string, unknown> | null;
  /** ISO timestamp of creation */
  created_at: string;
};

/**
 * Handlers for chat message subscription events.
 */
export type ChatMessageHandlers = {
  /** Called when a new chat message is inserted */
  onInsert?: (message: ChatMessage) => void;
  /** Called when a chat message is updated */
  onUpdate?: (message: ChatMessage) => void;
  /** Called when a chat message is deleted */
  onDelete?: (message: ChatMessage) => void;
};

/**
 * Subscribes to chat message changes via Supabase Realtime.
 *
 * Can filter by session ID or owner ID. Receives INSERT, UPDATE, and
 * DELETE events from the public.chat_messages table.
 *
 * @param client - Supabase client to use
 * @param ownerId - Owner (user) ID to filter messages
 * @param handlers - Callbacks for insert/update/delete events
 * @param sessionId - Optional session ID for finer filtering
 * @returns The Realtime channel for the subscription
 *
 * @example
 * ```typescript
 * const channel = subscribeToChatMessages(client, 'user-123', {
 *   onInsert: (msg) => {
 *     if (msg.role === 'agent') {
 *       console.log(`${msg.agent}: ${msg.content}`);
 *     }
 *   },
 * });
 * ```
 */
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

/**
 * Fetches chat messages for an owner from public.chat_messages.
 *
 * @param client - Supabase client to use
 * @param ownerId - Owner (user) ID to fetch messages for
 * @param options - Optional filters for limit and session
 * @returns Array of chat messages ordered by creation time (ascending)
 * @throws Supabase error if the query fails
 *
 * @example
 * ```typescript
 * const messages = await fetchChatMessages(client, 'user-123', {
 *   sessionId: 'session-456',
 *   limit: 50,
 * });
 * ```
 */
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

/**
 * Inserts a new chat message into public.chat_messages.
 *
 * @param client - Supabase client to use
 * @param message - Message data with required owner_id, role, and content
 * @returns The inserted chat message record
 * @throws Supabase error if the insert fails
 *
 * @example
 * ```typescript
 * const msg = await insertChatMessage(client, {
 *   owner_id: 'user-123',
 *   role: 'user',
 *   content: 'Hello, agent!',
 *   session_id: 'session-456',
 * });
 * ```
 */
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

/**
 * Source types for ingestion queue items.
 */
export type IngestionSourceType =
  | 'youtube'
  | 'pdf'
  | 'url'
  | 'upload'
  | 'notebook'
  | 'discord'
  | 'telegram'
  | 'rss';

/**
 * Status values for ingestion queue items.
 */
export type IngestionStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'processing'
  | 'completed'
  | 'failed';

/**
 * Represents an item in the public.ingestion_queue table.
 *
 * Items flow through statuses: pending → approved → processing → completed/failed
 * Or: pending → rejected
 */
export type IngestionQueueItem = {
  /** UUID primary key */
  id: string;
  /** Owner (user) ID, nullable for system-generated items */
  owner_id: string | null;
  /** Type of content source */
  source_type: IngestionSourceType;
  /** URL of the content source */
  source_url: string | null;
  /** External ID (e.g., YouTube video ID) */
  source_id: string | null;
  /** Content title */
  title: string | null;
  /** Content description */
  description: string | null;
  /** Thumbnail URL for preview */
  thumbnail_url: string | null;
  /** Duration in seconds (for video/audio) */
  duration_seconds: number | null;
  /** Source-specific metadata */
  source_meta: Record<string, unknown>;
  /** Current processing status */
  status: IngestionStatus;
  /** Priority level (higher = sooner) */
  priority: number;
  /** User ID who approved the item */
  approved_by: string | null;
  /** ISO timestamp of approval */
  approved_at: string | null;
  /** Reason for rejection (if rejected) */
  rejection_reason: string | null;
  /** ID of the processor handling this item */
  processor_id: string | null;
  /** ISO timestamp when processing started */
  processing_started_at: string | null;
  /** ISO timestamp when processing completed */
  processed_at: string | null;
  /** Error message if processing failed */
  error_message: string | null;
  /** Number of processing retries */
  retry_count: number;
  /** References to output artifacts */
  output_refs: Record<string, unknown>;
  /** ISO timestamp of creation */
  created_at: string;
  /** ISO timestamp of last update */
  updated_at: string;
};

/**
 * Handlers for ingestion queue subscription events.
 */
export type IngestionQueueHandlers = {
  /** Called when a new item is added to the queue */
  onInsert?: (item: IngestionQueueItem) => void;
  /** Called when an item is updated (status change, etc.) */
  onUpdate?: (item: IngestionQueueItem) => void;
  /** Called when an item is deleted */
  onDelete?: (item: IngestionQueueItem) => void;
};

/**
 * Subscribes to ingestion queue changes via Supabase Realtime.
 *
 * Can optionally filter by status. Receives INSERT, UPDATE, and DELETE
 * events from the public.ingestion_queue table.
 *
 * @param client - Supabase client to use
 * @param handlers - Callbacks for insert/update/delete events
 * @param statusFilter - Optional status filter (e.g., 'pending')
 * @returns The Realtime channel for the subscription
 *
 * @example
 * ```typescript
 * // Subscribe to all pending items
 * const channel = subscribeToIngestionQueue(client, {
 *   onInsert: (item) => console.log('New item:', item.title),
 *   onUpdate: (item) => console.log('Updated:', item.id, item.status),
 * }, 'pending');
 * ```
 */
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

/**
 * Fetches items from the ingestion queue with optional filters.
 *
 * Results are ordered by priority (descending) then creation time (ascending).
 *
 * @param client - Supabase client to use
 * @param options - Optional filters for status, source type, pagination
 * @returns Array of ingestion queue items
 * @throws Supabase error if the query fails
 *
 * @example
 * ```typescript
 * // Fetch pending YouTube videos
 * const items = await fetchIngestionQueue(client, {
 *   status: 'pending',
 *   sourceType: 'youtube',
 *   limit: 20,
 * });
 * ```
 */
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

/**
 * Approves an ingestion queue item for processing.
 *
 * Calls the approve_ingestion RPC function which:
 * - Sets status to 'approved'
 * - Records the approver and timestamp
 * - Optionally updates the priority
 *
 * @param client - Supabase client to use
 * @param id - UUID of the item to approve
 * @param priority - Optional new priority level
 * @returns The updated item, or null if not found
 * @throws Supabase error if the RPC fails
 *
 * @example
 * ```typescript
 * const approved = await approveIngestion(client, 'item-uuid', 10);
 * if (approved) {
 *   console.log('Approved:', approved.title);
 * }
 * ```
 */
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

/**
 * Rejects an ingestion queue item.
 *
 * Calls the reject_ingestion RPC function which:
 * - Sets status to 'rejected'
 * - Records the rejection reason
 *
 * @param client - Supabase client to use
 * @param id - UUID of the item to reject
 * @param reason - Optional reason for rejection
 * @returns The updated item, or null if not found
 * @throws Supabase error if the RPC fails
 *
 * @example
 * ```typescript
 * await rejectIngestion(client, 'item-uuid', 'Duplicate content');
 * ```
 */
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

/**
 * Fetches aggregated statistics for the ingestion queue.
 *
 * Calls the get_ingestion_stats RPC function which returns
 * counts grouped by status and source type.
 *
 * @param client - Supabase client to use
 * @returns Array of stats with status, source_type, and count
 * @throws Supabase error if the RPC fails
 *
 * @example
 * ```typescript
 * const stats = await fetchIngestionStats(client);
 * const pendingYouTube = stats.find(
 *   s => s.status === 'pending' && s.source_type === 'youtube'
 * );
 * console.log('Pending YouTube videos:', pendingYouTube?.count ?? 0);
 * ```
 */
export async function fetchIngestionStats(
  client: SupabaseClient
): Promise<Array<{ status: IngestionStatus; source_type: IngestionSourceType; count: number }>> {
  const { data, error } = await client.rpc('get_ingestion_stats');

  if (error) {
    throw error;
  }

  return (data ?? []) as Array<{ status: IngestionStatus; source_type: IngestionSourceType; count: number }>;
}
