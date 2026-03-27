import Link from 'next/link';
import { DashboardShell } from '@/components/DashboardNavigation';
import { loadRooms, type RoomDefinition } from '@/lib/rooms';

export const dynamic = 'force-dynamic';

function formatToken(value: string | undefined): string {
  if (!value) {
    return 'unset';
  }

  return value.replace(/[-_.]/g, ' ');
}

function summarizePanels(room: RoomDefinition): string {
  return room.manifest.shell.layout.panels.map((panel) => panel.kind).join(' / ');
}

export default async function RoomsPage() {
  const rooms = await loadRooms();
  const totalApps = rooms.reduce((sum, room) => sum + room.manifest.apps.length, 0);
  const totalSkills = rooms.reduce((sum, room) => sum + room.manifest.skill_bindings.filter((binding) => binding.enabled !== false).length, 0);
  const notebookProviders = new Set(rooms.map((room) => room.manifest.notebook.provider));

  return (
    <DashboardShell
      title="Rooms"
      subtitle="Agent-owned room shells loaded from the PMOVES room catalog"
      active="rooms"
      actions={
        <Link href="/api/rooms" className="tag tag-cyan">
          JSON API
        </Link>
      }
    >
      <div className="p-6 lg:p-8 space-y-8">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="card-brutal border border-cata-cyan/30 p-4">
            <div className="font-pixel text-[7px] uppercase tracking-wider text-cata-cyan">Rooms</div>
            <div className="mt-3 font-display text-3xl font-bold">{rooms.length}</div>
            <p className="mt-2 text-sm text-ink-secondary">Seeded room profiles available to the launcher and workbench.</p>
          </div>
          <div className="card-brutal border border-cata-forest/30 p-4">
            <div className="font-pixel text-[7px] uppercase tracking-wider text-cata-forest">Apps</div>
            <div className="mt-3 font-display text-3xl font-bold">{totalApps}</div>
            <p className="mt-2 text-sm text-ink-secondary">Declared app surfaces bound into room shells.</p>
          </div>
          <div className="card-brutal border border-cata-gold/30 p-4">
            <div className="font-pixel text-[7px] uppercase tracking-wider text-cata-gold">Skills</div>
            <div className="mt-3 font-display text-3xl font-bold">{totalSkills}</div>
            <p className="mt-2 text-sm text-ink-secondary">Enabled skill bindings ready for room-local invocation.</p>
          </div>
          <div className="card-brutal border border-cata-violet/30 p-4">
            <div className="font-pixel text-[7px] uppercase tracking-wider text-cata-violet">Notebook Providers</div>
            <div className="mt-3 font-display text-3xl font-bold">{notebookProviders.size}</div>
            <p className="mt-2 text-sm text-ink-secondary">Notebook backplanes currently represented in the catalog.</p>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          {rooms.map((room) => {
            const accent = room.manifest.shell.theme.accent_color ?? '#22C55E';
            const glyph = room.manifest.persona?.glyph ?? room.display_name.charAt(0).toUpperCase();
            const pinnedApps = room.manifest.apps.filter((app) => app.pinned);
            const activeSkills = room.manifest.skill_bindings.filter((binding) => binding.enabled !== false);

            return (
              <article
                key={room.room_id}
                className="card-brutal border p-6 flex flex-col gap-5"
                style={{ borderColor: accent, boxShadow: `0 0 0 1px ${accent}22` }}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="font-pixel text-[7px] uppercase tracking-[0.22em]" style={{ color: accent }}>
                      {room.agent_id}
                      {room.alter ? ` / ${room.alter}` : ''}
                    </div>
                    <div>
                      <h2 className="font-display text-2xl font-bold leading-tight text-ink-primary">
                        {room.display_name}
                      </h2>
                      <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
                        {room.summary ?? room.manifest.description ?? 'Room manifest loaded from catalog.'}
                      </p>
                    </div>
                  </div>

                  <div
                    className="flex h-12 w-12 shrink-0 items-center justify-center border text-xl font-display font-bold"
                    style={{ borderColor: accent, backgroundColor: `${accent}12`, color: accent }}
                    aria-hidden="true"
                  >
                    {glyph}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <span className="tag tag-forest">{formatToken(room.manifest.room_type)}</span>
                  <span className="tag tag-violet">{formatToken(room.manifest.owner_mode)}</span>
                  <span className="tag tag-gold">{formatToken(room.manifest.policies.model_routing)}</span>
                </div>

                <dl className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-ink-muted">Default route</dt>
                    <dd className="mt-1 font-mono text-xs text-ink-primary">{room.manifest.shell.layout.default_route}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-muted">Workspace</dt>
                    <dd className="mt-1 font-mono text-xs text-ink-primary">{room.manifest.notebook.workspace_ref}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-muted">Panels</dt>
                    <dd className="mt-1 text-ink-primary">{room.manifest.shell.layout.panels.length} ({summarizePanels(room)})</dd>
                  </div>
                  <div>
                    <dt className="text-ink-muted">Writeback</dt>
                    <dd className="mt-1 text-ink-primary">{room.manifest.notebook.sync.writeback_targets.join(', ')}</dd>
                  </div>
                </dl>

                <div className="space-y-2">
                  <div className="font-pixel text-[7px] uppercase tracking-[0.18em] text-ink-muted">Pinned apps</div>
                  <div className="flex flex-wrap gap-2">
                    {pinnedApps.map((app) => (
                      <Link
                        key={app.app_id}
                        href={app.route}
                        className="border border-border-subtle bg-void-soft px-2.5 py-1 font-mono text-2xs uppercase tracking-wider text-ink-secondary transition-colors hover:border-ink-primary hover:text-ink-primary"
                      >
                        {app.app_id}
                      </Link>
                    ))}
                    {pinnedApps.length === 0 && (
                      <span className="font-mono text-2xs uppercase tracking-wider text-ink-muted">No pinned apps</span>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="font-pixel text-[7px] uppercase tracking-[0.18em] text-ink-muted">Skill bindings</div>
                  <div className="space-y-2">
                    {activeSkills.slice(0, 2).map((binding) => (
                      <div key={binding.binding_id} className="border border-border-subtle bg-void-soft px-3 py-2">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-ink-primary">{binding.display_name}</span>
                          <span className="font-mono text-2xs uppercase tracking-wider text-ink-muted">
                            {binding.execution?.mode ?? 'direct'}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-ink-secondary">{binding.intent.join(', ')}</p>
                      </div>
                    ))}
                    {activeSkills.length === 0 && (
                      <div className="border border-border-subtle bg-void-soft px-3 py-2 text-xs text-ink-muted">
                        No enabled bindings in this room.
                      </div>
                    )}
                    {activeSkills.length > 2 && (
                      <div className="font-mono text-2xs uppercase tracking-wider text-ink-muted">
                        +{activeSkills.length - 2} more bindings in manifest
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-auto flex items-center justify-between gap-3 border-t border-border-subtle pt-4">
                  <Link
                    href={room.manifest.shell.layout.default_route}
                    className="inline-flex items-center gap-2 border px-3 py-2 text-xs font-mono uppercase tracking-wider transition-colors hover:text-void"
                    style={{ borderColor: accent, color: accent }}
                  >
                    Launch room
                  </Link>
                  <Link
                    href={`/api/rooms?room_id=${encodeURIComponent(room.room_id)}`}
                    className="font-mono text-2xs uppercase tracking-wider text-ink-secondary transition-colors hover:text-ink-primary"
                  >
                    Manifest JSON
                  </Link>
                </div>
              </article>
            );
          })}
        </section>

        {rooms.length === 0 && (
          <div className="card-brutal border border-border-subtle p-6 text-sm text-ink-secondary">
            No room manifests were found. Seed the catalog under <code>pmoves/config/rooms</code> and reload the dashboard.
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
