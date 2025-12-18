"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";
import {
  getSupabaseRealtimeClient,
  subscribeToChatMessages,
  type ChatMessage,
} from "../../../lib/realtimeClient";
import { logForDebugging, getErrorMessage } from "../../../lib/errorUtils";

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

type FetchResult = {
  data: ChatMessage[];
  error: string | null;
};

async function fetchMessages(): Promise<FetchResult> {
  try {
    const res = await fetch('/api/chat/messages', { cache: 'no-store' });
    if (!res.ok) {
      let body: Record<string, unknown> = {};
      try {
        body = await res.json();
      } catch (parseError) {
        logForDebugging('Failed to parse error response JSON', parseError, {
          component: 'chat/page',
          status: res.status,
        });
      }
      const errorMsg = (body.error as string) || getErrorMessage(res.status);
      logForDebugging('fetchMessages failed', new Error(errorMsg), {
        component: 'chat/page',
        status: res.status,
      });
      return { data: [], error: errorMsg };
    }
    const j = await res.json();
    return { data: (j.items ?? []) as ChatMessage[], error: null };
  } catch (e) {
    logForDebugging('fetchMessages network error', e, { component: 'chat/page' });
    return { data: [], error: 'Network error. Please check your connection.' };
  }
}

type SendResult = {
  ok: boolean;
  error: string | null;
};

async function sendMessage(content: string, agentId?: string): Promise<SendResult> {
  try {
    const res = await fetch('/api/chat/send', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ content, role: 'user', agent: agentId })
    });
    if (!res.ok) {
      let body: Record<string, unknown> = {};
      try {
        body = await res.json();
      } catch (parseError) {
        logForDebugging('Failed to parse send error response', parseError, {
          component: 'chat/page',
          status: res.status,
        });
      }
      return { ok: false, error: (body.error as string) || getErrorMessage(res.status) };
    }
    const body = await res.json();
    return { ok: body.ok ?? true, error: body.error ?? null };
  } catch (e) {
    logForDebugging('sendMessage network error', e, { component: 'chat/page' });
    return { ok: false, error: 'Network error. Please try again.' };
  }
}

export default function ChatDashboardPage() {
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [targetAgent, setTargetAgent] = useState<string>('agent-zero');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const channelRef = useRef<ReturnType<typeof subscribeToChatMessages> | null>(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [msgs]);

  // Setup Realtime subscription
  useEffect(() => {
    let isMounted = true;
    let pollingInterval: NodeJS.Timeout | null = null;

    const setupRealtime = async () => {
      // Set connecting status at start of async operation
      if (isMounted) setStatus('connecting');

      try {
        // Initial fetch
        const { data: initialMsgs, error: fetchError } = await fetchMessages();
        if (isMounted) {
          setMsgs(initialMsgs);
          if (fetchError) {
            setErrorMsg(fetchError);
          }
        }

        // Setup Realtime subscription
        const client = getSupabaseRealtimeClient();

        // Get owner_id from auth context or use session-based filtering
        // TODO: Replace with actual auth context when authentication is implemented
        // For now, we rely on RLS policies to filter messages appropriately
        const ownerId = typeof window !== 'undefined'
          ? localStorage.getItem('pmoves_user_id') || 'anonymous'
          : 'anonymous';

        const channel = subscribeToChatMessages(client, ownerId, {
          onInsert: (message) => {
            try {
              if (isMounted) {
                setMsgs((prev) => {
                  // Avoid duplicates
                  if (prev.some((m) => m.id === message.id)) {
                    return prev;
                  }
                  return [...prev, message];
                });
              }
            } catch (callbackError) {
              logForDebugging('Realtime onInsert callback error', callbackError, {
                component: 'chat/page',
                messageId: message?.id,
              });
            }
          },
          onUpdate: (message) => {
            try {
              if (isMounted) {
                setMsgs((prev) =>
                  prev.map((m) => (m.id === message.id ? message : m))
                );
              }
            } catch (callbackError) {
              logForDebugging('Realtime onUpdate callback error', callbackError, {
                component: 'chat/page',
                messageId: message?.id,
              });
            }
          },
          onDelete: (message) => {
            try {
              if (isMounted) {
                setMsgs((prev) => prev.filter((m) => m.id !== message.id));
              }
            } catch (callbackError) {
              logForDebugging('Realtime onDelete callback error', callbackError, {
                component: 'chat/page',
                messageId: message?.id,
              });
            }
          },
        });

        channelRef.current = channel;
        setStatus('connected');
      } catch (error) {
        logForDebugging('Failed to setup realtime', error, { component: 'chat/page' });
        if (isMounted) {
          setStatus('error');
          // Fallback to polling when realtime fails
          const load = async () => {
            const { data: m, error } = await fetchMessages();
            if (isMounted) {
              setMsgs(m);
              if (error) setErrorMsg(error);
            }
          };
          pollingInterval = setInterval(load, 3000);
        }
      }
    };

    setupRealtime();

    return () => {
      isMounted = false;
      // Clean up polling interval if it was created
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
      if (channelRef.current) {
        const client = getSupabaseRealtimeClient();
        client.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, []);

  const handleSend = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const content = input.trim();
    if (!content || sending) return;

    // Clear any previous error
    setErrorMsg(null);
    setSending(true);

    const result = await sendMessage(content, targetAgent);

    if (result.ok) {
      // Only clear input after successful send
      setInput('');
      // Fetch messages to show the new message immediately
      // (Realtime subscription will also receive it, but fetch ensures visibility)
      const { data: m, error: fetchError } = await fetchMessages();
      setMsgs(m);
      if (fetchError) setErrorMsg(fetchError);
    } else {
      // Keep input so user can retry, show error
      setErrorMsg(result.error || 'Failed to send message. Please try again.');
    }

    setSending(false);
  }, [input, targetAgent, sending]);

  const statusColor = {
    connecting: 'bg-yellow-400',
    connected: 'bg-green-500',
    disconnected: 'bg-gray-400',
    error: 'bg-red-500',
  }[status];

  const statusText = {
    connecting: 'Connecting...',
    connected: 'Live',
    disconnected: 'Disconnected',
    error: 'Connection Error (polling)',
  }[status];

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="chat" />
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Realtime Chat</h1>
          <div className="flex items-center gap-1.5 text-xs">
            <span className={`w-2 h-2 rounded-full ${statusColor} animate-pulse`} />
            <span className="text-neutral-500">{statusText}</span>
          </div>
        </div>
        <p className="text-sm text-neutral-600">
          Chat with PMOVES agents in real-time. Messages sync instantly via Supabase Realtime.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {/* Chat Panel */}
        <div className="md:col-span-2 rounded-lg border border-neutral-200 bg-white shadow-sm flex flex-col h-[600px]">
          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-4 space-y-4"
          >
            {msgs.length === 0 ? (
              <div className="text-sm text-neutral-500 text-center py-8">
                No messages yet. Start a conversation with an agent!
              </div>
            ) : (
              msgs.map((m) => (
                <div
                  key={m.id}
                  className={`flex items-start gap-3 ${
                    m.role === 'user' ? 'flex-row-reverse' : ''
                  }`}
                >
                  <Image
                    src={m.avatar_url || (m.role === 'agent' ? '/avatars/agent.svg' : '/avatars/owner.svg')}
                    alt={m.agent || m.role}
                    width={36}
                    height={36}
                    className="h-9 w-9 rounded-full border border-neutral-200 flex-shrink-0"
                    sizes="36px"
                  />
                  <div
                    className={`max-w-[75%] rounded-lg px-4 py-2 ${
                      m.role === 'user'
                        ? 'bg-slate-900 text-white'
                        : 'bg-neutral-100 text-neutral-900'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium ${
                        m.role === 'user' ? 'text-slate-300' : 'text-neutral-500'
                      }`}>
                        {m.agent || m.role}
                      </span>
                      <span className={`text-xs ${
                        m.role === 'user' ? 'text-slate-400' : 'text-neutral-400'
                      }`}>
                        {new Date(m.created_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                      {m.message_type && m.message_type !== 'text' && (
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          m.role === 'user' ? 'bg-slate-700' : 'bg-neutral-200'
                        }`}>
                          {m.message_type}
                        </span>
                      )}
                    </div>
                    <div className="text-sm whitespace-pre-wrap">{m.content}</div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Input Area */}
          <div className="border-t border-neutral-200 p-4">
            {/* Error banner */}
            {errorMsg && (
              <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
                <span className="text-sm text-red-700">{errorMsg}</span>
                <button
                  type="button"
                  onClick={() => setErrorMsg(null)}
                  className="text-red-400 hover:text-red-600 text-lg leading-none"
                  aria-label="Dismiss error"
                >
                  &times;
                </button>
              </div>
            )}
            <form onSubmit={handleSend} className="flex gap-2">
              <select
                value={targetAgent}
                onChange={(e) => setTargetAgent(e.target.value)}
                disabled={sending}
                className="rounded-lg border border-neutral-200 px-3 py-2 text-sm bg-white disabled:opacity-50"
              >
                <option value="agent-zero">Agent Zero</option>
                <option value="archon">Archon</option>
                <option value="research">Research Agent</option>
                <option value="media">Media Processor</option>
              </select>
              <input
                id="chatMessage"
                name="chatMessage"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={sending}
                placeholder="Type a message..."
                className="flex-1 rounded-lg border border-neutral-200 px-4 py-2 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 disabled:opacity-50"
                autoComplete="off"
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-w-[72px]"
              >
                {sending ? 'Sending...' : 'Send'}
              </button>
            </form>
            <p className="mt-2 text-xs text-neutral-400">
              Press Enter to send. Messages are delivered to agents via NATS.
            </p>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Agent Status */}
          <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-medium mb-3">Active Agents</h3>
            <div className="space-y-2">
              {[
                { id: 'agent-zero', name: 'Agent Zero', status: 'online', port: 8080 },
                { id: 'archon', name: 'Archon', status: 'online', port: 8091 },
                { id: 'research', name: 'Research Agent', status: 'idle', port: null },
                { id: 'media', name: 'Media Processor', status: 'idle', port: null },
              ].map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        agent.status === 'online' ? 'bg-green-500' : 'bg-neutral-300'
                      }`}
                    />
                    <span>{agent.name}</span>
                  </div>
                  <span className="text-xs text-neutral-400">
                    {agent.status === 'online' ? `:${agent.port}` : agent.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Native UIs */}
          <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-medium mb-3">Native UIs</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <a
                  className="text-blue-600 hover:underline"
                  href={process.env.NEXT_PUBLIC_ARCHON_UI_URL || 'http://localhost:3737'}
                  target="_blank"
                  rel="noreferrer"
                >
                  Archon UI
                </a>
              </li>
              <li>
                <a
                  className="text-blue-600 hover:underline"
                  href={process.env.NEXT_PUBLIC_AGENT_ZERO_UI_URL || 'http://localhost:8081'}
                  target="_blank"
                  rel="noreferrer"
                >
                  Agent Zero UI
                </a>
              </li>
              <li>
                <a
                  className="text-blue-600 hover:underline"
                  href={process.env.NEXT_PUBLIC_TENSORZERO_UI_URL || 'http://localhost:4000'}
                  target="_blank"
                  rel="noreferrer"
                >
                  TensorZero UI
                </a>
              </li>
            </ul>
          </div>

          {/* Quick Actions */}
          <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-medium mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <button
                onClick={() => setInput('/help')}
                className="w-full text-left text-sm px-3 py-2 rounded bg-neutral-50 hover:bg-neutral-100 transition-colors"
              >
                /help - Show commands
              </button>
              <button
                onClick={() => setInput('/status')}
                className="w-full text-left text-sm px-3 py-2 rounded bg-neutral-50 hover:bg-neutral-100 transition-colors"
              >
                /status - System status
              </button>
              <button
                onClick={() => setInput('/ingest ')}
                className="w-full text-left text-sm px-3 py-2 rounded bg-neutral-50 hover:bg-neutral-100 transition-colors"
              >
                /ingest - Add content
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
