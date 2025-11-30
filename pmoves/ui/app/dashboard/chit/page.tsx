import DashboardNavigation from '@/components/DashboardNavigation';
import { getChitLiveData } from '@/lib/chit';

export const dynamic = 'force-dynamic';

function StatusBadge({ label, tone }: { label: string; tone: 'ok' | 'warn' | 'error' | 'info' }) {
  const base = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium';
  if (tone === 'ok') return <span className={`${base} bg-emerald-100 text-emerald-700`}>{label}</span>;
  if (tone === 'warn') return <span className={`${base} bg-amber-100 text-amber-700`}>{label}</span>;
  if (tone === 'error') return <span className={`${base} bg-rose-100 text-rose-700`}>{label}</span>;
  return <span className={`${base} bg-slate-100 text-slate-700`}>{label}</span>;
}

export default async function ChitLivePage() {
  const data = await getChitLiveData();

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-6">
      <DashboardNavigation active="chit" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">CHIT Live Status</h1>
        <p className="text-sm text-slate-600">
          Review the CHIT secrets manifest and confirm which environment targets are currently satisfied. Update your
          <code className="mx-1">pmoves/chit</code>
          bundle or regenerate environment files when required keys are missing.
        </p>
      </header>

      {data.error ? (
        <div className="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          Unable to load `secrets_manifest.yaml`. Ensure the file exists at <code>{data.manifestPath}</code>.
          <div className="mt-2 text-xs text-rose-700">Error: {data.error}</div>
        </div>
      ) : null}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase text-slate-500">Manifest entries</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{data.stats.total}</div>
          <p className="mt-1 text-xs text-slate-500">Total records in `secrets_manifest.yaml`</p>
        </div>
        <div className="rounded border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase text-slate-500">Required satisfied</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">
            {data.stats.required - data.stats.missingRequired} / {data.stats.required}
          </div>
          <p className="mt-1 text-xs text-slate-500">Environment targets populated for required entries</p>
        </div>
        <div className="rounded border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase text-slate-500">Optional missing</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{data.stats.optionalMissing}</div>
          <p className="mt-1 text-xs text-slate-500">Optional entries without values in the current environment</p>
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-medium text-slate-900">Bundle references</h2>
            <p className="text-xs text-slate-500">
              Manifest: <code>{data.manifestPath}</code>
            </p>
            {data.cgpFilePath ? (
              <p className="text-xs text-slate-500">
                CGP file: <code>{data.cgpFilePath}</code>{' '}
                {data.cgpFileExists ? (
                  <StatusBadge tone="ok" label="present" />
                ) : (
                  <StatusBadge tone="warn" label="missing" />
                )}
              </p>
            ) : null}
          </div>
          <div className="text-xs text-slate-500">
            {data.cgpFileExists ? (
              <span>CGP payload detected. Run <code>make env-setup</code> after rotating secrets.</span>
            ) : (
              <span>CGP payload not found. Regenerate with <code>pmoves mini secrets encode</code>.</span>
            )}
          </div>
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-600">
              <tr>
                <th className="px-4 py-3">Label</th>
                <th className="px-4 py-3">Required</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Targets</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.entries.map((entry) => {
                const tone: 'ok' | 'warn' | 'error' = entry.satisfied
                  ? 'ok'
                  : entry.required
                    ? 'error'
                    : 'warn';
                return (
                  <tr key={entry.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{entry.label}</div>
                      <div className="text-xs text-slate-500">{entry.id}</div>
                    </td>
                    <td className="px-4 py-3">
                      {entry.required ? <StatusBadge tone="info" label="required" /> : <StatusBadge tone="info" label="optional" />}
                    </td>
                    <td className="px-4 py-3">
                      {entry.satisfied ? (
                        <StatusBadge tone={tone} label="complete" />
                      ) : entry.required ? (
                        <StatusBadge tone={tone} label="missing" />
                      ) : (
                        <StatusBadge tone={tone} label="pending" />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ul className="space-y-1 text-xs text-slate-600">
                        {entry.targets.length === 0 ? (
                          <li className="text-slate-500">No targets defined</li>
                        ) : (
                          entry.targets.map((target, idx) => (
                            <li key={`${entry.id}-${target.key}-${target.file}-${idx}`} className="flex items-center gap-2">
                              <code>{target.key}</code>
                              {target.present ? (
                                <StatusBadge tone="ok" label="set" />
                              ) : (
                                <StatusBadge tone={entry.required ? 'error' : 'warn'} label="missing" />
                              )}
                              <span className="text-slate-400">({target.file})</span>
                            </li>
                          ))
                        )}
                      </ul>
                    </td>
                  </tr>
                );
              })}
              {data.entries.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-slate-500">
                    No manifest entries found.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
