import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import AvatarStack from './AvatarStack';
import { usePresenceContext } from './PresenceProvider';

export type ChatPanelProps = {
  className?: string;
  title?: string;
  placeholder?: string;
  enableAvatarStack?: boolean;
};

function classNames(...values: Array<string | undefined | false>) {
  return values.filter(Boolean).join(' ');
}

function formatTimestamp(value: string) {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (error) {
    return value;
  }
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  className,
  title = 'Collaboration Chat',
  placeholder = 'Share an update…',
  enableAvatarStack = true,
}) => {
  const { messages, agents, sendMessage, isSendingMessage, lastError, selfAgentId } =
    usePresenceContext();
  const [draft, setDraft] = useState('');
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [messages]
  );

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [sortedMessages]);

  const handleSubmit = useCallback(
    async (event?: FormEvent) => {
      event?.preventDefault();
      const content = draft.trim();
      if (!content) {
        return;
      }
      try {
        await sendMessage({ content });
        setDraft('');
      } catch (error) {
        // Errors surfaced through context state; no-op.
      }
    },
    [draft, sendMessage]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div
      className={classNames('pmoves-chat-panel', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 12,
        border: '1px solid #e2e8f0',
        backgroundColor: '#ffffff',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          borderBottom: '1px solid #e2e8f0',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <h2 style={{ fontSize: 14, fontWeight: 600, color: '#334155', margin: 0 }}>
          {title}
        </h2>
        {enableAvatarStack && <AvatarStack />}
      </div>
      <div
        ref={scrollContainerRef}
        className="pmoves-chat-messages"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        {sortedMessages.length === 0 ? (
          <p style={{ fontSize: 14, color: '#94a3b8', margin: 0 }}>
            No messages yet. Start the conversation!
          </p>
        ) : (
          sortedMessages.map((message) => {
            const authorId = (message.meta?.agent_id ?? message.meta?.agentId) as
              | string
              | undefined;
            const agent = authorId ? agents[authorId] : undefined;
            const isSelf = authorId === selfAgentId;
            const displayName = agent?.name ?? message.role ?? 'Collaborator';
            const tone = isSelf ? '#4f46e5' : '#1e293b';

            return (
              <div key={message.id} className="pmoves-chat-message">
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: tone }}>
                    {displayName}
                  </span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    {formatTimestamp(message.created_at)}
                  </span>
                </div>
                <div
                  style={{
                    marginTop: 4,
                    whiteSpace: 'pre-line',
                    fontSize: 14,
                    color: '#1e293b',
                  }}
                >
                  {message.content}
                </div>
              </div>
            );
          })
        )}
      </div>
      <form
        onSubmit={handleSubmit}
        style={{
          borderTop: '1px solid #e2e8f0',
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div
          style={{
            border: '1px solid #cbd5f5',
            borderRadius: 8,
            boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
            padding: '4px 0',
          }}
        >
          <textarea
            style={{
              width: '100%',
              height: 96,
              resize: 'none',
              border: 'none',
              outline: 'none',
              background: 'transparent',
              padding: '8px 12px',
              fontSize: 14,
              color: '#1e293b',
              fontFamily: 'inherit',
            }}
            placeholder={placeholder}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSendingMessage}
          />
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ fontSize: 12, color: '#94a3b8' }}>
            {lastError
              ? lastError.message
              : 'Press Enter to send, Shift+Enter for a new line.'}
          </div>
          <button
            type="submit"
            className="pmoves-chat-send"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 12px',
              fontSize: 14,
              fontWeight: 600,
              color: '#ffffff',
              backgroundColor: isSendingMessage ? '#9ca3af' : '#4f46e5',
              borderRadius: 8,
              border: 'none',
              cursor:
                isSendingMessage || !draft.trim() ? 'not-allowed' : 'pointer',
              opacity: isSendingMessage || !draft.trim() ? 0.6 : 1,
            }}
            disabled={isSendingMessage || !draft.trim()}
          >
            {isSendingMessage ? 'Sending…' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default ChatPanel;
