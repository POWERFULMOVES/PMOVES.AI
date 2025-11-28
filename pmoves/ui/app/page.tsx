import Link from 'next/link';

type Feature = {
  title: string;
  description: string;
  accent: string;
};

type ModuleTile = {
  title: string;
  blurb: string;
  capabilities: string[];
  href: string;
};

type PipelineStage = {
  title: string;
  summary: string;
  highlight: string;
};

type PersonaAvatar = {
  name: string;
  role: string;
  theme: string;
  description: string;
};

type LinkDef = { label: string; href: string; health?: string; optional?: boolean };

const features: Feature[] = [
  {
    title: 'Cymatic Storyweaving',
    description:
      'Visualize resonance: sound-reactive plots show how data pulses across PMOVES, making invisible flows tangible for every collaborator.',
    accent: 'var(--cataclysm-cyan)',
  },
  {
    title: 'Geometry Bus',
    description:
      'Align holographic schemas, blueprint automations, and choreograph supply chains with the geometry-first logic core of PMOVES.',
    accent: 'var(--cataclysm-gold)',
  },
  {
    title: 'Chit System',
    description:
      'Tokenize commitments, route resources, and surface accountability loops that let communities move with precision and care.',
    accent: 'var(--cataclysm-ember)',
  },
];

const modules: ModuleTile[] = [
  {
    title: 'Agent Zero · Conversational Core',
    blurb:
      'Natural language entry point that orchestrates Supabase data, creative automations, and infrastructure workflows.',
    capabilities: ['Command console', 'Task delegation', 'Observability traces'],
    href: '/dashboard/agent-zero',
  },
  {
    title: 'Archon · Knowledge & Personas',
    blurb: 'Surface project knowledge, persona prompts, and geometry constellations for guided research.',
    capabilities: ['Persona studio', 'Explainability', 'Geometry exports'],
    href: '/dashboard/archon',
  },
  {
    title: 'Creator Pipeline · ComfyUI to Publish',
    blurb:
      'Ingest renders, audio, and storyboards with the MinIO + Supabase loop documented in the Creator Pipeline runbook.',
    capabilities: ['ComfyUI uploads', 'Supabase approvals', 'Discord & Jellyfin publish'],
    href: '/dashboard/ingest',
  },
  {
    title: 'Notebook Workbench · Model Ops',
    blurb: 'Manage runtime catalogs, seed embeddings, and test inference routes from any device.',
    capabilities: ['Model registry', 'Runtime diagnostics', 'GPU / CPU failover'],
    href: '/dashboard/notebook',
  },
  {
    title: 'Finance & Health · Automations',
    blurb:
      'Monitor Firefly III and Wger data streams translated into CGPs so squads can act on weekly insights.',
    capabilities: ['Supabase sync', 'CGP visualizations', 'Cost-aware prompts'],
    href: '/dashboard/services',
  },
  {
    title: 'Monitoring & Observability',
    blurb: 'Grafana, Prometheus, and Channel Monitor dashboards ensure distributed services stay aligned.',
    capabilities: ['Health badges', 'Latency probes', 'Alert routing'],
    href: '/dashboard/monitor',
  },
];

const pipeline: PipelineStage[] = [
  {
    title: 'Create & Upload',
    summary: 'ComfyUI renders assets and pushes them to MinIO with the PMOVES upload nodes.',
    highlight: 'GPU-assisted render bundles, uv-managed environments, and tagged filenames keep the flow deterministic.',
  },
  {
    title: 'Webhook → Supabase',
    summary: 'Render Webhook stamps studio_board rows, handing metadata to Supabase for approvals.',
    highlight: 'Auto-approve toggles and namespace conventions align assets with geometry constellations.',
  },
  {
    title: 'Review & Approve',
    summary: 'Operators triage submissions in the Studio Board and apply persona-aligned feedback.',
    highlight: 'Tags funnel into Indexer facets so creator squads can search, remix, and federate outputs.',
  },
  {
    title: 'Publish & Broadcast',
    summary: 'Publisher emits Discord embeds, refreshes Jellyfin, and mirrors CGPs on the Geometry Bus.',
    highlight: 'Audit logs and Chit signals prove where every asset travels across the PMOVES mesh.',
  },
];

const personas: PersonaAvatar[] = [
  {
    name: 'Archon',
    role: 'Knowledge Strategist',
    theme: 'Neo-library Cyberpunk',
    description:
      'Guides research constellations, narrates geometry jumps, and keeps persona prompts coherent across missions.',
  },
  {
    name: 'Catalyst',
    role: 'Creator Pipeline Lead',
    theme: 'Megaman Pixel Synth',
    description:
      'Animates ComfyUI drops, syncs VibeVoice narrations, and frames CGP rituals with cymatic flair.',
  },
  {
    name: 'Ledger',
    role: 'Finance & Ops Steward',
    theme: 'Retro Futurist Analogue',
    description:
      'Balances Firefly insights, Wger check-ins, and Chit commitments so collectives stay accountable.',
  },
];

function HeroSection() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-6 py-20 text-slate-100">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute inset-0 opacity-60 blur-3xl">
          <div className="absolute left-1/4 top-10 h-72 w-72 rounded-full bg-[var(--cataclysm-cyan)]/40 mix-blend-screen" />
          <div className="absolute right-1/5 top-1/3 h-96 w-96 rounded-full bg-[var(--cataclysm-forest)]/30 mix-blend-screen" />
          <div className="absolute left-1/2 bottom-10 h-80 w-80 rounded-full bg-[var(--cataclysm-ember)]/25 mix-blend-screen" />
        </div>
        <div className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-[var(--cataclysm-gold)]/10 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(31,184,205,0.12),rgba(10,10,20,0.9))]" />
        <div className="absolute inset-0 opacity-40">
          <svg className="h-full w-full" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="grid" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(210,186,76,0.25)" />
                <stop offset="100%" stopColor="rgba(31,184,205,0.15)" />
              </linearGradient>
            </defs>
            <path d="M0 100 Q150 120 300 100 T600 100" stroke="rgba(45,197,253,0.2)" strokeWidth="0.5" />
            <path d="M0 200 Q180 230 300 200 T600 200" stroke="rgba(210,186,76,0.25)" strokeWidth="0.5" />
            <path d="M0 300 Q120 320 300 300 T600 300" stroke="rgba(62,178,116,0.2)" strokeWidth="0.5" />
            <path d="M0 400 Q160 430 300 400 T600 400" stroke="rgba(219,69,69,0.2)" strokeWidth="0.5" />
            <path d="M0 500 Q200 520 300 500 T600 500" stroke="rgba(93,135,143,0.25)" strokeWidth="0.5" />
            <path d="M100 0 Q120 150 100 300 T100 600" stroke="url(#grid)" strokeWidth="0.4" />
            <path d="M220 0 Q240 160 220 320 T220 600" stroke="url(#grid)" strokeWidth="0.4" />
            <path d="M340 0 Q360 200 340 360 T340 600" stroke="url(#grid)" strokeWidth="0.4" />
            <path d="M460 0 Q480 170 460 340 T460 600" stroke="url(#grid)" strokeWidth="0.4" />
          </svg>
        </div>
      </div>

      <div className="relative z-10 flex w-full max-w-4xl flex-col items-center gap-10 text-center">
        <span className="inline-flex items-center justify-center rounded-full border border-white/20 bg-white/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.32em] text-[var(--cataclysm-gold)]">
          Cataclysm Studios Inc.
        </span>
        <div className="space-y-6">
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl">Powerful Moves for everyday creators</h1>
          <p className="mx-auto max-w-3xl text-base text-slate-200 sm:text-xl">
            From <strong className="text-[var(--cataclysm-cyan)]">CATACLYSM STUDIOS INC.</strong> and the POWERFULMOVES initiative comes a symphony of cymatics, holography, and precision geometry. PMOVES orchestrates the Chit System, Geometry Bus, and cooperative automations so collectives can prototype, publish, and scale together.
          </p>
          <p className="mx-auto max-w-2xl text-sm text-slate-300 sm:text-lg">
            Explore <strong className="text-[var(--cataclysm-gold)]">PMOVES.AI</strong> for the full capability atlas, tap into <strong className="text-[var(--cataclysm-forest)]">cataclsmtudios.com</strong> for the studio constellation, and connect via the Cataclysm home lab network spanning cataclsysmstudios.net.
          </p>
        </div>

        <div className="flex w-full flex-col items-center justify-center gap-4 sm:w-auto sm:flex-row">
          <Link
            href="/community"
            className="inline-flex w-full items-center justify-center rounded-full bg-[var(--cataclysm-cyan)] px-8 py-3 text-sm font-semibold uppercase tracking-wide text-slate-950 shadow-[0_18px_40px_-18px_rgba(31,184,205,0.9)] transition duration-200 ease-out hover:scale-[1.02] hover:bg-[var(--cataclysm-forest)] hover:text-white hover:shadow-[0_22px_50px_-20px_rgba(46,139,87,0.9)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cataclysm-gold)] focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 sm:w-auto"
          >
            Join the creator community
          </Link>
          <Link
            href="/login?next=%2Fdashboard%2Fingest"
            className="inline-flex w-full items-center justify-center rounded-full bg-[var(--cataclysm-ember)] px-8 py-3 text-sm font-semibold uppercase tracking-wide text-white shadow-[0_18px_40px_-18px_rgba(219,69,69,0.9)] transition duration-200 ease-out hover:scale-[1.02] hover:bg-[var(--cataclysm-gold)] hover:text-slate-900 hover:shadow-[0_22px_50px_-20px_rgba(210,186,76,0.95)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cataclysm-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 sm:w-auto"
          >
            Launch engineer console
          </Link>
        </div>

        <div className="grid w-full gap-6 text-left sm:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-lg backdrop-blur"
              style={{ boxShadow: `0 20px 45px -20px ${feature.accent}26` }}
            >
              <h2 className="text-lg font-semibold" style={{ color: feature.accent }}>
                {feature.title}
              </h2>
              <p className="mt-3 text-sm text-slate-200">{feature.description}</p>
            </div>
          ))}
        </div>

        <p className="text-xs uppercase tracking-[0.3em] text-[var(--cataclysm-slate)]">
          Cyan · Ember · Forest · Gold — the Cataclysm palette guiding every move.
        </p>
      </div>
    </section>
  );
}

function UnifiedModulesSection() {
  return (
    <section className="bg-white px-6 py-20 text-slate-900">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-12">
        <header className="flex flex-col gap-4 text-center">
          <span className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--cataclysm-slate)]">
            Unified Portal · Modular Reach
          </span>
          <h2 className="text-3xl font-bold sm:text-4xl">
            Everything in PMOVES is reachable from one surface
          </h2>
          <p className="mx-auto max-w-3xl text-base text-slate-600 sm:text-lg">
            The console blends conversational orchestration, knowledge navigation, creator automations, and operational health in a
            responsive layout aligned with the unified UI design story. Choose a module to dive deeper or hand off tasks to Agent Zero.
          </p>
        </header>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {modules.map((module) => (
            <a
              key={module.title}
              href={module.href}
              className="group flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
            >
              <div>
                <h3 className="text-xl font-semibold text-slate-900">{module.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{module.blurb}</p>
              </div>
              <ul className="mt-auto grid grid-cols-1 gap-2 text-sm text-slate-700">
                {module.capabilities.map((capability) => (
                  <li
                    key={`${module.title}-${capability}`}
                    className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium uppercase tracking-wide text-slate-600 group-hover:border-[var(--cataclysm-cyan)] group-hover:text-[var(--cataclysm-cyan)]"
                  >
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--cataclysm-cyan)]" aria-hidden />
                    {capability}
                  </li>
                ))}
              </ul>
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--cataclysm-cyan)] group-hover:text-[var(--cataclysm-ember)]">
                Explore module →
              </span>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

function CreatorPipelineSection() {
  return (
    <section className="bg-slate-950 px-6 py-20 text-slate-100">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
        <header className="text-center">
          <span className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--cataclysm-gold)]">
            Creator Pipeline · ComfyUI → Publish
          </span>
          <h2 className="mt-4 text-3xl font-bold text-white sm:text-4xl">Launch the full creative flywheel</h2>
          <p className="mx-auto mt-4 max-w-3xl text-base text-slate-300 sm:text-lg">
            The documented Creator Pipeline keeps renders, voices, and geometry aligned. Follow the loop to move assets from ComfyUI rigs to
            Supabase approvals and onward to Discord, Jellyfin, and geometry constellations without losing context.
          </p>
        </header>
        <ol className="relative grid gap-8 border-l border-white/10 pl-6 sm:pl-10">
          {pipeline.map((stage, index) => (
            <li key={stage.title} className="relative flex flex-col gap-3">
              <div className="absolute -left-[1.95rem] top-1.5 flex h-8 w-8 items-center justify-center rounded-full border border-white/30 bg-[var(--cataclysm-cyan)]/20 text-sm font-semibold text-[var(--cataclysm-gold)] sm:-left-[2.7rem]">
                {index + 1}
              </div>
              <h3 className="text-xl font-semibold text-white">{stage.title}</h3>
              <p className="text-sm text-slate-200">{stage.summary}</p>
              <p className="text-xs uppercase tracking-wide text-[var(--cataclysm-cyan)]">{stage.highlight}</p>
            </li>
          ))}
        </ol>
        <div className="flex flex-col items-center justify-center gap-3 text-center text-sm text-slate-300 sm:flex-row">
          <a
            href="https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/docs/Unified%20and%20Modular%20PMOVES%20UI%20Design.md"
            className="rounded-full border border-white/20 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-[var(--cataclysm-cyan)] hover:border-[var(--cataclysm-gold)] hover:text-[var(--cataclysm-gold)]"
          >
            UI design manifesto
          </a>
          <span className="hidden h-px w-10 bg-white/20 sm:block" aria-hidden />
          <a
            href="https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVES.AI%20PLANS/CREATOR_PIPELINE.md"
            className="rounded-full border border-white/20 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-[var(--cataclysm-gold)] hover:border-[var(--cataclysm-cyan)] hover:text-[var(--cataclysm-cyan)]"
          >
            Creator pipeline runbook
          </a>
        </div>
      </div>
    </section>
  );
}

function PersonaShowcaseSection() {
  return (
    <section className="bg-white px-6 py-20 text-slate-900">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
        <header className="text-center">
          <span className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--cataclysm-slate)]">
            Avatars & Voice Signatures
          </span>
          <h2 className="mt-3 text-3xl font-bold sm:text-4xl">Give every agent a face and a vibe</h2>
          <p className="mx-auto mt-4 max-w-3xl text-base text-slate-600 sm:text-lg">
            Personas align with the avatar guidance in the unified UI plan. Style presets keep artwork cohesive across CGPs, chat, and
            voice drops—ready for ComfyUI regeneration or VibeVoice playback at any moment.
          </p>
        </header>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {personas.map((persona) => (
            <div
              key={persona.name}
              className="relative flex h-full flex-col gap-4 overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 p-6 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-sm font-semibold uppercase tracking-wide text-[var(--cataclysm-ember)]">
                    {persona.role}
                  </span>
                  <h3 className="text-2xl font-bold text-slate-900">{persona.name}</h3>
                </div>
                <div className="flex h-14 w-14 items-center justify-center rounded-full border border-[var(--cataclysm-cyan)]/40 bg-[var(--cataclysm-cyan)]/10 text-lg font-semibold text-[var(--cataclysm-cyan)]">
                  {persona.name.slice(0, 1)}
                </div>
              </div>
              <p className="text-sm text-slate-600">{persona.description}</p>
              <div className="mt-auto rounded-2xl border border-dashed border-[var(--cataclysm-gold)]/50 bg-[var(--cataclysm-gold)]/10 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--cataclysm-gold)]">
                Theme · {persona.theme}
              </div>
            </div>
          ))}
        </div>
        <p className="text-center text-xs uppercase tracking-[0.25em] text-[var(--cataclysm-slate)]">
          Swap presets via creator pipelines · Keep voices synced with VibeVoice + RVC bundles
        </p>
      </div>
    </section>
  );
}

async function probe(url?: string) {
  if (!url) return undefined;
  try {
    const res = await fetch(url, { next: { revalidate: 0 } });
    return res.ok;
  } catch {
    return false;
  }
}

function getDashboardLinks(): LinkDef[] {
  const gpuPort = process.env.HIRAG_V2_GPU_HOST_PORT || '8087';
  const agentZeroBase = (process.env.NEXT_PUBLIC_AGENT_ZERO_URL || 'http://localhost:8080').replace(/\/$/, '');
  const archonBase = (process.env.NEXT_PUBLIC_ARCHON_URL || 'http://localhost:8091').replace(/\/$/, '');
  const jellyfinBase = (process.env.NEXT_PUBLIC_JELLYFIN_URL || 'http://localhost:8096').replace(/\/$/, '');
  const supaserchPort = process.env.SUPASERCH_HOST_PORT || process.env.SUPASERCH_PORT || '8099';
  const supaserchBase = (process.env.NEXT_PUBLIC_SUPASERCH_URL || `http://localhost:${supaserchPort}`).replace(/\/$/, '');

  return [
    { label: 'Notebook dashboard', href: '/dashboard/notebook' },
    { label: 'Notebook workbench', href: '/notebook-workbench', optional: true },
    { label: 'Notebook runtime', href: '/dashboard/notebook/runtime', optional: true },
    { label: 'Personas', href: '/dashboard/personas' },
    { label: 'Chit live', href: '/dashboard/chit', optional: true },
    {
      label: 'Agent Zero',
      href: '/dashboard/agent-zero',
      health: (() => {
        const custom = (process.env.NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH || '').trim();
        if (!custom) return `${agentZeroBase}/healthz`;
        return custom.startsWith('/') ? `${agentZeroBase}${custom}` : `${agentZeroBase}/${custom}`;
      })(),
    },
    {
      label: 'Archon',
      href: '/dashboard/archon',
      health: (() => {
        const custom = (process.env.NEXT_PUBLIC_ARCHON_HEALTH_PATH || '').trim();
        if (!custom) return `${archonBase}/healthz`;
        return custom.startsWith('/') ? `${archonBase}${custom}` : `${archonBase}/${custom}`;
      })(),
    },
    {
      label: 'SupaSerch',
      href: '/dashboard/services/supaserch',
      health: `${supaserchBase}/healthz`,
    },
    {
      label: 'SupaSerch metrics',
      href: `${supaserchBase}/metrics`,
      optional: true,
      health: `${supaserchBase}/metrics`,
    },
    {
      label: 'Hi‑RAG Geometry (GPU)',
      href: `http://localhost:${gpuPort}/geometry/`,
      health: `http://localhost:${gpuPort}/hirag/admin/stats`,
    },
    {
      label: 'TensorZero UI (4000)',
      href: process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000',
      health: process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000',
    },
    {
      label: 'TensorZero Gateway (3030)',
      href: process.env.NEXT_PUBLIC_TENSORZERO_GATEWAY || 'http://localhost:3030',
      optional: true,
    },
    {
      label: 'Jellyfin (8096)',
      href: jellyfinBase,
      health: `${jellyfinBase}/System/Info`,
    },
    {
      label: 'Open Notebook (8503)',
      href: process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503',
      health: process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503',
    },
    {
      label: 'Supabase Studio (65433)',
      href: process.env.NEXT_PUBLIC_SUPABASE_STUDIO_URL || 'http://127.0.0.1:65433',
      health: process.env.NEXT_PUBLIC_SUPABASE_STUDIO_URL || 'http://127.0.0.1:65433',
    },
    {
      label: 'Invidious (3000)',
      href: process.env.NEXT_PUBLIC_INVIDIOUS_URL || 'http://127.0.0.1:3000',
      health: process.env.NEXT_PUBLIC_INVIDIOUS_URL || 'http://127.0.0.1:3000',
    },
  ];
}

function OperatorConsole({
  primaryHref,
  primaryLabel,
  links,
  statuses,
}: {
  primaryHref: string;
  primaryLabel: string;
  links: LinkDef[];
  statuses: Array<boolean | undefined>;
}) {
  return (
    <section className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-100 p-8 text-center">
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold text-slate-900">PMOVES Operator Console</h1>
        <p className="max-w-md text-sm text-slate-600">
          Sign in to manage ingestion workflows, upload new assets, and monitor Supabase processing pipelines.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href={primaryHref}
          className="rounded bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-slate-700"
        >
          {primaryLabel}
        </Link>
        <Link
          href="/dashboard/ingest"
          className="rounded border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400 hover:text-slate-900"
        >
          View ingestion dashboard
        </Link>
      </div>
      <div className="w-full max-w-5xl">
        <div className="mx-auto grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {links.map((link, idx) => {
            const health = link.health;
            const status = statuses[idx];
            const badge = health
              ? status === true
                ? (
                    <span className="ml-2 rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                      healthy
                    </span>
                  )
                : status === false
                  ? (
                      <span className="ml-2 rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">
                        down
                      </span>
                    )
                  : (
                      <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        n/a
                      </span>
                    )
              : (
                  <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    link
                  </span>
                );
            return (
              <a
                key={`${link.label}_${link.href}`}
                href={link.href}
                target={link.href.startsWith('http') ? '_blank' : undefined}
                rel={link.href.startsWith('http') ? 'noreferrer' : undefined}
                className="rounded border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium text-slate-800 shadow-sm hover:border-slate-300 hover:shadow"
              >
                {link.label}
                {badge}
                {link.optional ? (
                  <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    optional
                  </span>
                ) : null}
              </a>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default async function HomePage() {
  const hasBootJwt = Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT,
  );
  const primaryHref = hasBootJwt ? '/dashboard/ingest' : '/login';
  const primaryLabel = hasBootJwt ? 'Open dashboard' : 'Continue to login';
  const links = getDashboardLinks();
  const statuses = await Promise.all(links.map((link) => probe(link.health)));

  return (
    <>
      <HeroSection />
      <UnifiedModulesSection />
      <CreatorPipelineSection />
      <PersonaShowcaseSection />
      <OperatorConsole
        primaryHref={primaryHref}
        primaryLabel={primaryLabel}
        links={links}
        statuses={statuses}
      />
    </>
  );
}
