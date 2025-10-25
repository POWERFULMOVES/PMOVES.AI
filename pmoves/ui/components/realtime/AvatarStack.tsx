import React from 'react';
import { AgentProfile, usePresenceContext } from './PresenceProvider';

export type AvatarStackProps = {
  className?: string;
  maxVisible?: number;
  size?: number;
};

function classNames(...values: Array<string | undefined | false>) {
  return values.filter(Boolean).join(' ');
}

function getInitials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? '')
    .join('');
}

const Avatar: React.FC<{ agent: AgentProfile; size: number }> = ({
  agent,
  size,
}) => {
  const initials = getInitials(agent.name);
  const background = agent.color ?? '#1f2937';

  return (
    <div
      className="pmoves-avatar flex items-center justify-center rounded-full border-2 border-white text-xs font-semibold uppercase text-white shadow"
      style={{
        width: size,
        height: size,
        backgroundColor: background,
        overflow: 'hidden',
      }}
      title={agent.name}
    >
      {agent.avatarUrl ? (
        <img
          src={agent.avatarUrl}
          alt={agent.name}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        <span>{initials}</span>
      )}
    </div>
  );
};

export const AvatarStack: React.FC<AvatarStackProps> = ({
  className,
  maxVisible = 5,
  size = 32,
}) => {
  const { activeAgents } = usePresenceContext();

  if (!activeAgents.length) {
    return null;
  }

  const visibleAgents = activeAgents.slice(0, maxVisible);
  const overflow = activeAgents.length - visibleAgents.length;

  return (
    <div
      className={classNames('pmoves-avatar-stack', className)}
      style={{ display: 'flex', alignItems: 'center', gap: 12 }}
    >
      <div style={{ display: 'flex' }}>
        {visibleAgents.map((agent, index) => (
          <div
            key={agent.id}
            style={{ marginLeft: index === 0 ? 0 : -size / 3 }}
          >
            <Avatar agent={agent} size={size} />
          </div>
        ))}
      </div>
      {overflow > 0 && (
        <span style={{ fontSize: 12, color: '#64748b' }}>+{overflow}</span>
      )}
    </div>
  );
};

export default AvatarStack;
