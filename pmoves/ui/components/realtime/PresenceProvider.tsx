import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';
import {
  CursorPosition,
  MessageRecord,
  PresenceStateMap,
  SupabaseRealtimeConfig,
  fetchSessionMessages,
  getServiceRoleClient,
  getSupabaseRealtimeClient,
  insertSessionMessage,
  subscribeToBoardPresence,
  subscribeToSessionMessages,
} from '../../lib/realtimeClient';

export type AgentProfile = {
  id: string;
  name: string;
  role?: string | null;
  avatarUrl?: string | null;
  color?: string | null;
  meta: Record<string, any>;
};

export type CursorDatum = {
  agentId: string;
  position: CursorPosition;
  label: string;
  color?: string | null;
  lastSeenAt: string;
};

export type SendMessageInput = {
  content: string;
  role?: MessageRecord['role'];
  meta?: Record<string, any>;
  tokens?: number | null;
};

export type PresenceContextValue = {
  boardId: string;
  sessionId: string;
  selfAgentId: string;
  presence: PresenceStateMap;
  agents: Record<string, AgentProfile>;
  activeAgents: AgentProfile[];
  cursors: CursorDatum[];
  messages: MessageRecord[];
  isSendingMessage: boolean;
  lastError: Error | null;
  sendMessage: (input: SendMessageInput) => Promise<MessageRecord | null>;
  updateCursor: (cursor: CursorPosition | null) => Promise<void>;
  client: SupabaseClient;
};

export type PresenceProviderProps = {
  boardId: string;
  sessionId: string;
  selfAgentId: string;
  children: React.ReactNode;
  supabaseConfig?: SupabaseRealtimeConfig;
  initialCursor?: CursorPosition | null;
  initialAgents?: AgentProfile[];
  initialMessages?: MessageRecord[];
  messageWriter?: (
    payload: Omit<MessageRecord, 'id' | 'created_at'>
  ) => Promise<MessageRecord>;
};

const PresenceContext = createContext<PresenceContextValue | undefined>(
  undefined
);

const COLOR_PALETTE = [
  '#6366f1',
  '#ec4899',
  '#22d3ee',
  '#f59e0b',
  '#10b981',
  '#a855f7',
];

function pickColor(agentId: string, override?: string | null) {
  if (override) {
    return override;
  }
  const hash = Array.from(agentId).reduce(
    (acc, char) => acc + char.charCodeAt(0),
    0
  );
  return COLOR_PALETTE[hash % COLOR_PALETTE.length];
}

function normaliseAgent(data: any): AgentProfile {
  const meta = (data?.meta ?? {}) as Record<string, any>;
  const avatarUrl = meta.avatar_url ?? meta.avatarUrl ?? null;
  const color = meta.color ?? null;
  return {
    id: data.id,
    name: data.name ?? 'Unknown Agent',
    role: data.role ?? null,
    avatarUrl,
    color,
    meta,
  };
}

function upsertMessage(
  list: MessageRecord[],
  entry: MessageRecord
): MessageRecord[] {
  const index = list.findIndex((item) => item.id === entry.id);
  if (index === -1) {
    return [...list, entry].sort((a, b) =>
      a.created_at.localeCompare(b.created_at)
    );
  }

  const next = [...list];
  next[index] = entry;
  return next.sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export function usePresenceContext(): PresenceContextValue {
  const value = useContext(PresenceContext);
  if (!value) {
    throw new Error('usePresenceContext must be used within a PresenceProvider');
  }
  return value;
}

export const PresenceProvider: React.FC<PresenceProviderProps> = ({
  boardId,
  sessionId,
  selfAgentId,
  children,
  supabaseConfig,
  initialCursor = null,
  initialAgents = [],
  initialMessages = [],
  messageWriter,
}) => {
  const supabaseUrl = supabaseConfig?.supabaseUrl;
  const anonKey = supabaseConfig?.anonKey;
  const serviceRoleKey = supabaseConfig?.serviceRoleKey;

  const client = useMemo(
    () => getSupabaseRealtimeClient({ supabaseUrl, anonKey }),
    [supabaseUrl, anonKey]
  );

  const serviceClient = useMemo(() => {
    if (!serviceRoleKey) {
      return null;
    }
    return getServiceRoleClient({ supabaseUrl, anonKey, serviceRoleKey });
  }, [supabaseUrl, anonKey, serviceRoleKey]);

  const presenceSubscriptionRef = useRef<ReturnType<
    typeof subscribeToBoardPresence
  > | null>(null);
  const messageChannelRef = useRef<ReturnType<
    typeof subscribeToSessionMessages
  > | null>(null);

  const [presence, setPresence] = useState<PresenceStateMap>({});
  const [agents, setAgents] = useState<Record<string, AgentProfile>>(() => {
    return initialAgents.reduce<Record<string, AgentProfile>>((acc, agent) => {
      acc[agent.id] = agent;
      return acc;
    }, {});
  });
  const [messages, setMessages] = useState<MessageRecord[]>(initialMessages);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [lastError, setLastError] = useState<Error | null>(null);

  useEffect(() => {
    const subscription = subscribeToBoardPresence(client, {
      boardId,
      presenceKey: selfAgentId,
      initialPayload: {
        session_id: sessionId,
        cursor: initialCursor,
        meta: { agent_id: selfAgentId },
      },
      onStateChange: (state) => {
        setPresence(state);
      },
    });

    presenceSubscriptionRef.current = subscription;

    return () => {
      subscription.unsubscribe().catch((error) => {
        console.warn('Failed to unsubscribe from presence channel', error);
      });
    };
  }, [client, boardId, selfAgentId, initialCursor]);

  useEffect(() => {
    let isMounted = true;

    const loadMessages = async () => {
      try {
        const data = await fetchSessionMessages(client, sessionId);
        if (isMounted && data) {
          setMessages(data);
        }
      } catch (error) {
        console.warn('Unable to load session messages', error);
      }
    };

    if (!initialMessages.length) {
      loadMessages();
    }

    const channel = subscribeToSessionMessages(client, sessionId, {
      onInsert: (message) => {
        setMessages((prev) => upsertMessage(prev, message));
      },
      onUpdate: (message) => {
        setMessages((prev) => upsertMessage(prev, message));
      },
      onDelete: (message) => {
        setMessages((prev) => prev.filter((item) => item.id !== message.id));
      },
    });

    messageChannelRef.current = channel;

    return () => {
      isMounted = false;
      client.removeChannel(channel);
    };
  }, [client, sessionId, initialMessages.length]);

  const fetchAgents = useCallback(
    async (ids: string[]) => {
      if (!ids.length) {
        return;
      }

      const unique = ids.filter((id, index) => ids.indexOf(id) === index);
      const missing = unique.filter((id) => !agents[id]);
      if (!missing.length) {
        return;
      }

      const { data, error } = await client
        .from('pmoves_core.agent')
        .select('id, name, role, meta')
        .in('id', missing);

      if (error) {
        console.warn('Failed to load agent profiles', error);
        return;
      }

      const nextAgents = (data ?? []).map(normaliseAgent);
      setAgents((prev) => {
        const next = { ...prev };
        nextAgents.forEach((agent) => {
          next[agent.id] = agent;
        });
        return next;
      });
    },
    [client, agents]
  );

  useEffect(() => {
    const presenceIds = Object.values(presence).map((item) => item.agentId);
    const messageIds = messages
      .map((message) => message.meta?.agent_id ?? message.meta?.agentId)
      .filter((value): value is string => Boolean(value));
    fetchAgents([...presenceIds, ...messageIds]);
  }, [presence, messages, fetchAgents]);

  useEffect(() => {
    fetchAgents([selfAgentId]);
  }, [fetchAgents, selfAgentId]);

  useEffect(() => {
    const profile = agents[selfAgentId];
    if (!profile || !presenceSubscriptionRef.current) {
      return;
    }

    presenceSubscriptionRef.current
      .updatePresence({
        meta: {
          ...(profile.meta ?? {}),
          name: profile.name,
          color: profile.color ?? pickColor(selfAgentId),
          agent_id: selfAgentId,
        },
      })
      .catch((error) => {
        console.warn('Failed to broadcast agent metadata', error);
      });
  }, [agents, selfAgentId]);

  const updateCursor = useCallback(
    async (cursor: CursorPosition | null) => {
      if (!presenceSubscriptionRef.current) {
        return;
      }

      try {
        await presenceSubscriptionRef.current.updatePresence({ cursor });
      } catch (error) {
        console.warn('Failed to update cursor presence', error);
      }
    },
    []
  );

  const sendMessage = useCallback(
    async (input: SendMessageInput) => {
      if (!input.content?.trim()) {
        return null;
      }

      setIsSendingMessage(true);
      setLastError(null);

      const basePayload: Omit<MessageRecord, 'id' | 'created_at'> = {
        session_id: sessionId,
        role: input.role ?? 'user',
        content: input.content,
        tokens: input.tokens ?? null,
        meta: {
          ...(input.meta ?? {}),
          agent_id: selfAgentId,
        },
      };

      try {
        let message: MessageRecord;

        if (messageWriter) {
          message = await messageWriter(basePayload);
        } else {
          const writer = serviceClient ?? client;
          message = await insertSessionMessage(writer, basePayload);
        }

        setMessages((prev) => upsertMessage(prev, message));
        return message;
      } catch (error) {
        const err =
          error instanceof Error ? error : new Error('Unable to send message');
        setLastError(err);
        if (!serviceClient && !messageWriter) {
          console.error(
            'Message insert failed. Provide a service role key or messageWriter to bypass RLS.',
            error
          );
        }
        throw err;
      } finally {
        setIsSendingMessage(false);
      }
    },
    [client, serviceClient, messageWriter, sessionId, selfAgentId]
  );

  const activeAgents = useMemo(() => {
    return Object.values(presence)
      .map((participant) => {
        const profile = agents[participant.agentId];
        if (!profile) {
          return null;
        }

        const color = pickColor(
          participant.agentId,
          profile.color ?? (participant.meta?.color as string | undefined)
        );

        return {
          ...profile,
          color,
          meta: {
            ...profile.meta,
            lastSeenAt: participant.lastSeenAt,
            cursor: participant.cursor,
          },
        } satisfies AgentProfile;
      })
      .filter((value): value is AgentProfile => Boolean(value));
  }, [agents, presence]);

  const cursors = useMemo(() => {
    return Object.values(presence)
      .filter((entry) => Boolean(entry.cursor))
      .map((entry) => {
        const profile = agents[entry.agentId];
        const name = profile?.name ?? entry.meta?.name ?? 'Collaborator';
        const color = pickColor(
          entry.agentId,
          profile?.color ?? (entry.meta?.color as string | undefined)
        );
        return {
          agentId: entry.agentId,
          position: entry.cursor!,
          label: name,
          color,
          lastSeenAt: entry.lastSeenAt,
        } as CursorDatum;
      });
  }, [agents, presence]);

  const contextValue = useMemo<PresenceContextValue>(
    () => ({
      boardId,
      sessionId,
      selfAgentId,
      presence,
      agents,
      activeAgents,
      cursors,
      messages,
      isSendingMessage,
      lastError,
      sendMessage,
      updateCursor,
      client,
    }),
    [
      boardId,
      sessionId,
      selfAgentId,
      presence,
      agents,
      activeAgents,
      cursors,
      messages,
      isSendingMessage,
      lastError,
      sendMessage,
      updateCursor,
      client,
    ]
  );

  return (
    <PresenceContext.Provider value={contextValue}>
      {children}
    </PresenceContext.Provider>
  );
};

export default PresenceProvider;
