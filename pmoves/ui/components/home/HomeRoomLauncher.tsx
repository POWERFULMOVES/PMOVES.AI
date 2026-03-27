'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

export type HomeRoomOption = {
  roomId: string;
  displayName: string;
  agentId: string;
  alter?: string;
  summary?: string;
  defaultRoute: string;
  accentColor?: string;
  glyph?: string;
  pinnedApps: Array<{
    appId: string;
    route: string;
  }>;
};

type HomeRoomLauncherProps = {
  rooms: HomeRoomOption[];
};

const STORAGE_KEY = 'pmoves.home.selectedRoom';

function getLoginHref(roomId: string): string {
  return `/login?room_id=${encodeURIComponent(roomId)}`;
}

export function HomeRoomLauncher({ rooms }: HomeRoomLauncherProps) {
  const [selectedRoomId, setSelectedRoomId] = useState(() => {
    if (typeof window !== 'undefined') {
      try {
        const storedRoomId = window.localStorage.getItem(STORAGE_KEY);
        if (storedRoomId && rooms.some((room) => room.roomId === storedRoomId)) {
          return storedRoomId;
        }
      } catch {
        // Ignore storage failures and fall back to the first room.
      }
    }

    return rooms[0]?.roomId ?? '';
  });

  const selectedRoom = useMemo(
    () => rooms.find((room) => room.roomId === selectedRoomId) ?? rooms[0] ?? null,
    [rooms, selectedRoomId]
  );

  useEffect(() => {
    if (!selectedRoom) {
      return;
    }

    try {
      window.localStorage.setItem(STORAGE_KEY, selectedRoom.roomId);
    } catch {
      // Ignore storage failures and keep the in-memory selection.
    }
  }, [selectedRoom]);

  if (!selectedRoom) {
    return (
      <div className="mt-10 max-w-3xl border border-border-subtle bg-void-elevated/80 p-5">
        <div className="font-pixel text-[8px] uppercase tracking-[0.2em] text-ink-muted">[ Room Launch ]</div>
        <p className="mt-3 text-sm text-ink-secondary">
          Room manifests are not available yet. Open the catalog once the room seeds are present.
        </p>
        <Link href="/dashboard/rooms" className="btn-ghost mt-4 inline-flex">
          Open room catalog
        </Link>
      </div>
    );
  }

  const accent = selectedRoom.accentColor ?? '#22C55E';

  return (
    <section className="mt-10 max-w-4xl border border-cata-cyan/20 bg-void-elevated/80 p-5 backdrop-blur-sm sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="font-pixel text-[8px] uppercase tracking-[0.2em] text-cata-cyan">[ Room Launch ]</div>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-secondary">
            Choose the room shell you want to enter. The selected room is carried through login and resolves to its declared entry route.
          </p>
        </div>
        <Link href="/dashboard/rooms" className="btn-ghost text-xs">
          Room Catalog
        </Link>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {rooms.map((room) => {
          const active = room.roomId === selectedRoom.roomId;
          const roomAccent = room.accentColor ?? '#22C55E';
          return (
            <button
              key={room.roomId}
              type="button"
              aria-pressed={active}
              onClick={() => setSelectedRoomId(room.roomId)}
              className="border px-3 py-2 text-left font-mono text-xs uppercase tracking-wider transition-all"
              style={{
                borderColor: active ? roomAccent : 'rgba(148, 163, 184, 0.25)',
                backgroundColor: active ? `${roomAccent}20` : 'rgba(15, 23, 42, 0.65)',
                color: active ? roomAccent : 'rgb(203 213 225)',
              }}
            >
              {room.displayName}
            </button>
          );
        })}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
        <div className="border border-border-subtle bg-void/80 p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="font-pixel text-[7px] uppercase tracking-[0.18em]" style={{ color: accent }}>
                {selectedRoom.agentId}
                {selectedRoom.alter ? ` / ${selectedRoom.alter}` : ''}
              </div>
              <h3 className="mt-2 font-display text-2xl font-bold text-ink-primary">{selectedRoom.displayName}</h3>
            </div>
            <div
              className="flex h-11 w-11 items-center justify-center border text-lg font-display font-bold"
              style={{ borderColor: accent, backgroundColor: `${accent}12`, color: accent }}
              aria-hidden="true"
            >
              {selectedRoom.glyph ?? selectedRoom.displayName.charAt(0).toUpperCase()}
            </div>
          </div>

          <p className="mt-3 text-sm leading-relaxed text-ink-secondary">
            {selectedRoom.summary ?? 'Room manifest loaded from the PMOVES catalog.'}
          </p>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="font-pixel text-[6px] uppercase tracking-[0.18em] text-ink-muted">Entry route</div>
              <div className="mt-2 font-mono text-xs text-ink-primary">{selectedRoom.defaultRoute}</div>
            </div>
            <div>
              <div className="font-pixel text-[6px] uppercase tracking-[0.18em] text-ink-muted">Pinned apps</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {selectedRoom.pinnedApps.length > 0 ? (
                  selectedRoom.pinnedApps.map((app) => (
                    <Link
                      key={app.appId}
                      href={app.route}
                      className="border border-border-subtle bg-void-soft px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink-secondary transition-colors hover:border-ink-primary hover:text-ink-primary"
                    >
                      {app.appId}
                    </Link>
                  ))
                ) : (
                  <span className="font-mono text-2xs uppercase tracking-wider text-ink-muted">No pinned apps</span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <Link
            href={getLoginHref(selectedRoom.roomId)}
            className="btn-primary text-center"
            aria-label={`Launch ${selectedRoom.displayName}`}
          >
            Launch {selectedRoom.displayName}
          </Link>
          <Link href={selectedRoom.defaultRoute} className="btn-secondary text-center">
            Preview Entry Route
          </Link>
          <div className="border border-border-subtle bg-void/70 p-3 text-xs text-ink-secondary">
            Selection is stored locally on this browser so the same room stays primed on return visits.
          </div>
        </div>
      </div>
    </section>
  );
}

