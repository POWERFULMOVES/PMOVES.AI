import React from 'react';
import { usePresenceContext } from './PresenceProvider';

export type CursorOverlayProps = {
  className?: string;
  showLabels?: boolean;
};

function classNames(...values: Array<string | undefined | false>) {
  return values.filter(Boolean).join(' ');
}

function clamp(value: number, min = 0, max = 1) {
  return Math.min(Math.max(value, min), max);
}

export const CursorOverlay: React.FC<CursorOverlayProps> = ({
  className,
  showLabels = true,
}) => {
  const { cursors } = usePresenceContext();

  if (!cursors.length) {
    return null;
  }

  return (
    <div
      className={classNames(
        'pmoves-cursor-overlay pointer-events-none absolute inset-0',
        className
      )}
      style={{
        pointerEvents: 'none',
        position: 'absolute',
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
      }}
    >
      {cursors.map((cursor) => {
        const left = `${clamp(cursor.position.x) * 100}%`;
        const top = `${clamp(cursor.position.y) * 100}%`;

        return (
          <div
            key={cursor.agentId}
            className="pmoves-cursor absolute flex flex-col items-center"
            style={{
              left,
              top,
              transform: 'translate(-50%, -50%)',
              color: cursor.color ?? '#6366f1',
            }}
          >
            <div
              className="pmoves-cursor-dot"
              style={{
                width: 12,
                height: 12,
                borderRadius: '9999px',
                backgroundColor: cursor.color ?? '#6366f1',
                boxShadow: '0 0 0 2px rgba(255,255,255,0.9)',
              }}
            />
            {showLabels && (
              <div
                className="pmoves-cursor-label mt-1 rounded px-2 py-1 text-xs font-medium text-white"
                style={{
                  backgroundColor: 'rgba(17, 24, 39, 0.75)',
                  whiteSpace: 'nowrap',
                }}
              >
                {cursor.label}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default CursorOverlay;
