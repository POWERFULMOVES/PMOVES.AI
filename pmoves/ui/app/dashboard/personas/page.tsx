import { getServiceSupabaseClient } from '@/lib/supabaseServer';
import type { Database } from '@/lib/database.types';
import DashboardNavigation from '../../../components/DashboardNavigation';

export const dynamic = 'force-dynamic';

type Persona = {
  name: string;
  version: string | number | null;
  description: string | null;
  runtime: Record<string, any> | null;
};

function coercePersona(input: any): Persona {
  const runtimeValue =
    input && typeof input.runtime === 'object' && !Array.isArray(input.runtime)
      ? (input.runtime as Record<string, any>)
      : null;
  return {
    name: typeof input?.name === 'string' ? input.name : String(input?.name ?? ''),
    version: typeof input?.version === 'number' || typeof input?.version === 'string' ? input.version : null,
    description: typeof input?.description === 'string' ? input.description : null,
    runtime: runtimeValue,
  };
}

const mapPersonaRow = (row: Database['pmoves_core']['Tables']['personas']['Row']): Persona =>
  coercePersona({
    name: row.name,
    version: row.version,
    description: row.description,
    runtime: row.runtime,
  });

async function fetchFromPostgrest(): Promise<{ data: Persona[]; error?: string }>
{
  const base = (process.env.POSTGREST_URL || 'http://localhost:3010').replace(/\/$/, '');
  const url = `${base}/personas?select=name,version,description,runtime&order=name.asc&limit=100`;
  try {
    const res = await fetch(url, {
      headers: {
        'Accept-Profile': 'pmoves_core',
        'Content-Profile': 'pmoves_core',
        ...(process.env.SUPABASE_SERVICE_ROLE_KEY ? { 'apikey': process.env.SUPABASE_SERVICE_ROLE_KEY, 'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}` } : {}),
      },
      next: { revalidate: 0 },
    });
    if (!res.ok) return { data: [], error: `PostgREST ${res.status}` };
    const rows = await res.json();
    const personas = Array.isArray(rows) ? rows.map(coercePersona) : [];
    return { data: personas };
  } catch (e: any) {
    return { data: [], error: e?.message || 'PostgREST fetch failed' };
  }
}

async function loadPersonas(): Promise<{ data: Persona[]; error?: string }>
{
  // Try supabase-js first (when SUPABASE_* points to a supabase-style base URL)
  try {
    const client = getServiceSupabaseClient();
    const { data, error } = await client
      .schema('pmoves_core')
      .from('personas')
      .select('name, version, description, runtime')
      .order('name')
      .limit(100);
    if (error) {
      // Fallback to direct PostgREST if schema isn’t exposed on the primary REST host
      const pg = await fetchFromPostgrest();
      return pg.data.length ? pg : { data: [], error: error.message };
    }
    return { data: (data ?? []).map(mapPersonaRow) };
  } catch (e: any) {
    // Attempt PostgREST fallback
    const pg = await fetchFromPostgrest();
    return pg.data.length ? pg : { data: [], error: e?.message || 'Unexpected error' };
  }
}

export default async function PersonasPage() {
  const { data, error } = await loadPersonas();
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-6">
      <DashboardNavigation active="personas" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Grounded Personas</h1>
        <p className="text-sm text-slate-600">
          Review the seeded persona definitions available to the cooperative runtime. Use the Supabase runbooks to seed
          additional personas before inviting collaborators.
        </p>
      </header>
      {error && (
        <div className="mb-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Unable to fetch personas from Supabase REST. If you are using the Supabase CLI
          PostgREST (65421) and it doesn’t expose the pmoves_core schema, either:
          <ul className="ml-5 list-disc">
            <li>Set <code>POSTGREST_URL</code> (e.g. <code>http://localhost:3010</code>) so the console can query PostgREST directly with <code>Accept-Profile: pmoves_core</code>.</li>
            <li>Or configure your primary REST to expose <code>public,pmoves_core</code> and keep using <code>SUPABASE_* </code> variables.</li>
          </ul>
          Error: {error}
        </div>
      )}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {data.map((p) => (
          <div key={`${p.name}-${p.version}`} className="rounded border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-medium text-slate-900">
              {p.name} <span className="ml-2 text-xs text-slate-500">v{String(p.version ?? '')}</span>
            </h2>
            {p.description && (
              <p className="mt-2 text-sm text-slate-600">{p.description}</p>
            )}
            {p.runtime && (
              <pre className="mt-3 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-700">
                {JSON.stringify(p.runtime, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {!error && data.length === 0 && (
          <div className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-600">
            No personas found yet. Re-run <code>make -C pmoves supabase-bootstrap</code> to seed v5.12 definitions.
          </div>
        )}
      </section>
    </div>
  );
}
