import Link from 'next/link';

/* ═══════════════════════════════════════════════════════════════════════════
   POWERFULMOVES Landing Page — Megaman × Transformers
   Cataclysm Studios Inc.
   ═══════════════════════════════════════════════════════════════════════════ */

type Module = {
  title: string;
  tag: string;
  tagColor: 'cyan' | 'ember' | 'gold' | 'forest' | 'violet';
  description: string;
  capabilities: string[];
  href: string;
  port?: string;
};

type PipelineStep = {
  num: string;
  title: string;
  description: string;
};

type Persona = {
  name: string;
  role: string;
  theme: string;
  initial: string;
  color: string;
};

type ServiceLink = {
  label: string;
  href: string;
  health?: string;
  port?: string;
};

const modules: Module[] = [
  {
    title: 'Agent Zero',
    tag: 'Orchestration',
    tagColor: 'cyan',
    description: 'Control-plane orchestrator with embedded agent runtime. MCP API gateway for external agent integration.',
    capabilities: ['MCP API', 'NATS JetStream', 'Task delegation'],
    href: '/dashboard/agent-zero',
    port: '8080',
  },
  {
    title: 'Archon',
    tag: 'Knowledge',
    tagColor: 'violet',
    description: 'Supabase-driven prompt studio with persona management and form generation for guided research.',
    capabilities: ['Persona studio', 'Prompt management', 'Forms'],
    href: '/dashboard/archon',
    port: '8091',
  },
  {
    title: 'Hi-RAG v2',
    tag: 'Retrieval',
    tagColor: 'forest',
    description: 'Hybrid RAG with cross-encoder reranking. Combines Qdrant vectors, Neo4j graph, and Meilisearch.',
    capabilities: ['Vector search', 'Graph traversal', 'Reranking'],
    href: '/dashboard/services/hi-rag',
    port: '8086',
  },
  {
    title: 'TensorZero',
    tag: 'Gateway',
    tagColor: 'gold',
    description: 'Centralized LLM gateway with ClickHouse observability. Token tracking, latency metrics, usage analytics.',
    capabilities: ['Multi-provider', 'Observability', 'Rate limiting'],
    href: '/dashboard/services/tensorzero',
    port: '3030',
  },
  {
    title: 'Creator Pipeline',
    tag: 'Media',
    tagColor: 'ember',
    description: 'ComfyUI to publish workflow. Ingest renders, audio, storyboards with MinIO + Supabase loop.',
    capabilities: ['ComfyUI uploads', 'Approvals', 'Discord publish'],
    href: '/dashboard/ingest',
  },
  {
    title: 'SupaSerch',
    tag: 'Research',
    tagColor: 'cyan',
    description: 'Multimodal holographic deep research orchestrator. Coordinates DeepResearch and MCP tools.',
    capabilities: ['Deep search', 'Multi-source', 'Auto-publish'],
    href: '/dashboard/services/supaserch',
    port: '8099',
  },
];

const pipeline: PipelineStep[] = [
  { num: '01', title: 'Create', description: 'ComfyUI renders assets and pushes to MinIO' },
  { num: '02', title: 'Webhook', description: 'Render webhook stamps studio_board rows' },
  { num: '03', title: 'Approve', description: 'Operators triage in Studio Board' },
  { num: '04', title: 'Publish', description: 'Emit to Discord, Jellyfin, Geometry Bus' },
];

const personas: Persona[] = [
  { name: 'Archon', role: 'Knowledge Strategist', theme: 'Neo-library Cyberpunk', initial: 'A', color: 'var(--cata-violet)' },
  { name: 'Catalyst', role: 'Creator Pipeline Lead', theme: 'Megaman Pixel Synth', initial: 'C', color: 'var(--cata-ember)' },
  { name: 'Ledger', role: 'Finance & Ops Steward', theme: 'Retro Futurist Analogue', initial: 'L', color: 'var(--cata-gold)' },
];

function getServiceLinks(): ServiceLink[] {
  const agentZeroBase = (process.env.NEXT_PUBLIC_AGENT_ZERO_URL || 'http://localhost:8080').replace(/\/$/, '');
  const archonBase = (process.env.NEXT_PUBLIC_ARCHON_URL || 'http://localhost:8091').replace(/\/$/, '');
  const supaserchPort = process.env.SUPASERCH_HOST_PORT || '8099';
  const supaserchBase = `http://localhost:${supaserchPort}`;
  const gpuPort = process.env.HIRAG_V2_GPU_HOST_PORT || '8087';

  return [
    { label: 'Agent Zero', href: '/dashboard/agent-zero', health: `${agentZeroBase}/healthz`, port: '8080' },
    { label: 'Archon', href: '/dashboard/archon', health: `${archonBase}/healthz`, port: '8091' },
    { label: 'Hi-RAG v2', href: `http://localhost:${gpuPort}/geometry/`, health: `http://localhost:${gpuPort}/hirag/admin/stats`, port: gpuPort },
    { label: 'TensorZero', href: process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000', port: '4000' },
    { label: 'SupaSerch', href: '/dashboard/services/supaserch', health: `${supaserchBase}/healthz`, port: supaserchPort },
    { label: 'Grafana', href: 'http://localhost:3000', port: '3000' },
    { label: 'Prometheus', href: 'http://localhost:9090', port: '9090' },
    { label: 'Jellyfin', href: process.env.NEXT_PUBLIC_JELLYFIN_URL || 'http://localhost:8096', port: '8096' },
    { label: 'Open Notebook', href: process.env.NEXT_PUBLIC_OPEN_NOTEBOOK_URL || 'http://localhost:8503', port: '8503' },
    { label: 'Supabase', href: process.env.NEXT_PUBLIC_SUPABASE_STUDIO_URL || 'http://127.0.0.1:65433', port: '65433' },
  ];
}

async function probe(url?: string): Promise<boolean | undefined> {
  if (!url) return undefined;
  try {
    const res = await fetch(url, { next: { revalidate: 0 } });
    return res.ok;
  } catch {
    return false;
  }
}

/* ─────────────────────────────────────────────────────────────────────────────
   Hero Section — Megaman × Transformers Style
   ───────────────────────────────────────────────────────────────────────────── */

function HeroSection() {
  return (
    <section className="relative min-h-screen overflow-hidden scanline">
      {/* Background layers */}
      <div className="cymatic-grid" />
      <div className="absolute inset-0 pointer-events-none">
        {/* Floating orbs */}
        <div className="absolute top-20 left-[10%] w-96 h-96 rounded-full bg-cata-cyan/20 blur-[100px] animate-pulse-glow" />
        <div className="absolute bottom-40 right-[15%] w-80 h-80 rounded-full bg-cata-ember/15 blur-[80px] animate-pulse-glow" style={{ animationDelay: '-2s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-cata-violet/10 blur-[120px] animate-pulse-glow" style={{ animationDelay: '-4s' }} />
      </div>

      <div className="relative z-10 flex flex-col min-h-screen">
        {/* Nav */}
        <nav className="flex items-center justify-between px-6 py-6 lg:px-12">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-cata-cyan corner-cut" />
            <span className="font-display font-bold text-sm tracking-widest">PMOVES</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <Link href="/community" className="font-display text-xs uppercase tracking-wider text-ink-secondary hover:text-cata-cyan transition-colors">Community</Link>
            <Link href="/dashboard/services" className="font-display text-xs uppercase tracking-wider text-ink-secondary hover:text-cata-cyan transition-colors">Services</Link>
            <Link href="https://github.com/POWERFULMOVES/PMOVES.AI" className="font-display text-xs uppercase tracking-wider text-ink-secondary hover:text-cata-cyan transition-colors">GitHub</Link>
          </div>
          <Link
            href="/login?next=%2Fdashboard%2Fingest"
            className="btn-primary"
          >
            Launch Console
          </Link>
        </nav>

        {/* Hero content */}
        <div className="flex-1 flex flex-col justify-center px-6 lg:px-12 pb-24">
          {/* Eyebrow - pixel style */}
          <div className="mb-8 opacity-0 animate-fade-in-up">
            <span className="font-pixel text-[8px] text-cata-gold tracking-wider">
              [ CATACLYSM STUDIOS INC ]
            </span>
          </div>

          {/* Main headline - Transformers style */}
          <h1 className="opacity-0 animate-fade-in-up delay-100">
            <span className="heading-display text-5xl sm:text-7xl lg:text-8xl xl:text-[10rem] block text-chrome">
              POWERFUL
            </span>
            <span className="heading-display text-5xl sm:text-7xl lg:text-8xl xl:text-[10rem] block text-gradient-cyan mt-2">
              MOVES
            </span>
          </h1>

          {/* Tagline - pixel accent */}
          <div className="mt-8 opacity-0 animate-fade-in-up delay-200">
            <p className="font-pixel text-[10px] text-cata-cyan tracking-wide">
              FOR EVERYDAY CREATORS
            </p>
          </div>

          {/* Subhead */}
          <p className="mt-8 max-w-2xl text-lg text-ink-secondary leading-relaxed opacity-0 animate-fade-in-up delay-300 font-body">
            60+ microservice orchestration platform featuring autonomous agents,
            hybrid RAG, and multimodal deep research. From{' '}
            <strong className="text-cata-cyan font-semibold">cymatic storyweaving</strong> to{' '}
            <strong className="text-cata-gold font-semibold">geometry bus</strong> coordination.
          </p>

          {/* CTA row */}
          <div className="mt-10 flex flex-wrap gap-4 opacity-0 animate-fade-in-up delay-400">
            <Link href="/community" className="btn-pixel">
              Join Community
            </Link>
            <Link href="/dashboard/notebook" className="btn-secondary">
              Explore Notebook
            </Link>
          </div>

          {/* Stats strip - mech style */}
          <div className="mt-16 flex flex-wrap gap-8 lg:gap-16 opacity-0 animate-fade-in-up delay-500">
            <div className="card-mech p-4 min-w-[120px]">
              <div className="font-display text-3xl font-bold text-cata-cyan">60+</div>
              <div className="font-pixel text-[6px] text-ink-muted uppercase mt-2">Microservices</div>
            </div>
            <div className="card-mech p-4 min-w-[120px]">
              <div className="font-display text-3xl font-bold text-cata-forest">43+</div>
              <div className="font-pixel text-[6px] text-ink-muted uppercase mt-2">Slash Commands</div>
            </div>
            <div className="card-mech p-4 min-w-[120px]">
              <div className="font-display text-3xl font-bold text-cata-gold">5</div>
              <div className="font-pixel text-[6px] text-ink-muted uppercase mt-2">Network Tiers</div>
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 opacity-0 animate-fade-in-up delay-600">
          <span className="font-pixel text-[6px] text-ink-muted uppercase">Scroll</span>
          <div className="w-px h-12 bg-gradient-to-b from-cata-cyan to-transparent" />
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Modules Grid Section
   ───────────────────────────────────────────────────────────────────────────── */

function ModulesSection() {
  const tagColors: Record<string, string> = {
    cyan: 'tag-cyan',
    ember: 'tag-ember',
    gold: 'tag-gold',
    forest: 'tag-forest',
    violet: 'text-cata-violet bg-cata-violet/10 border-cata-violet',
  };

  return (
    <section className="relative py-32 px-6 lg:px-12 bg-void-elevated">
      {/* Section header */}
      <div className="max-w-7xl mx-auto mb-16">
        <div className="flex items-end justify-between gap-8 flex-wrap">
          <div>
            <span className="font-pixel text-[8px] text-cata-cyan tracking-wider mb-4 block">
              [ PLATFORM MODULES ]
            </span>
            <h2 className="heading-display text-4xl sm:text-5xl lg:text-6xl mt-4">
              EVERYTHING FROM
              <br />
              <span className="text-gradient-violet">ONE SURFACE</span>
            </h2>
          </div>
          <p className="max-w-md text-ink-secondary font-body">
            Conversational orchestration, knowledge navigation, creator automations,
            and operational health in a responsive mesh.
          </p>
        </div>
        <div className="line-accent w-full mt-12" />
      </div>

      {/* Modules grid */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {modules.map((mod, idx) => (
          <Link
            key={mod.title}
            href={mod.href}
            className="group card-mech p-6 flex flex-col gap-4"
            style={{ animationDelay: `${idx * 100}ms` }}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className={`tag ${tagColors[mod.tagColor]}`}>{mod.tag}</span>
                <h3 className="font-display font-bold text-lg mt-3 group-hover:text-cata-cyan transition-colors uppercase tracking-wide">
                  {mod.title}
                </h3>
              </div>
              {mod.port && (
                <span className="font-mono text-2xs text-ink-muted bg-void px-2 py-1">
                  :{mod.port}
                </span>
              )}
            </div>

            {/* Description */}
            <p className="text-sm text-ink-secondary leading-relaxed flex-1 font-body">
              {mod.description}
            </p>

            {/* Capabilities */}
            <div className="flex flex-wrap gap-2 mt-auto pt-4 border-t border-border-subtle">
              {mod.capabilities.map((cap) => (
                <span
                  key={cap}
                  className="font-pixel text-[6px] text-ink-muted uppercase bg-void-soft px-2 py-1"
                >
                  {cap}
                </span>
              ))}
            </div>

            {/* Hover indicator */}
            <div className="flex items-center gap-2 text-xs text-ink-muted group-hover:text-cata-cyan transition-colors mt-2">
              <span className="font-display text-xs uppercase tracking-wider">Explore</span>
              <span className="transform group-hover:translate-x-1 transition-transform">&rarr;</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Pipeline Section
   ───────────────────────────────────────────────────────────────────────────── */

function PipelineSection() {
  return (
    <section className="relative py-32 px-6 lg:px-12">
      {/* Background accent */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute right-0 top-1/4 w-1/3 h-1/2 bg-glow-ember opacity-20 blur-[150px]" />
      </div>

      <div className="relative max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-8 mb-20">
          <div>
            <span className="font-pixel text-[8px] text-cata-ember tracking-wider mb-4 block">
              [ CREATOR PIPELINE ]
            </span>
            <h2 className="heading-display text-4xl sm:text-5xl lg:text-6xl mt-4">
              COMFYUI
              <span className="text-ink-muted mx-3">&rarr;</span>
              <span className="text-gradient-ember">PUBLISH</span>
            </h2>
          </div>
          <div className="lg:text-right max-w-md">
            <p className="text-ink-secondary font-body">
              Launch the full creative flywheel. Renders, voices, and geometry
              aligned through the documented pipeline.
            </p>
            <Link href="/dashboard/ingest" className="btn-ghost mt-4">
              View pipeline <span>&rarr;</span>
            </Link>
          </div>
        </div>

        {/* Pipeline steps */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-px bg-border-subtle">
          {pipeline.map((step) => (
            <div
              key={step.num}
              className="bg-void p-8 group hover:bg-void-elevated transition-colors"
            >
              <span className="font-display text-6xl font-bold text-border-subtle group-hover:text-cata-ember transition-colors">
                {step.num}
              </span>
              <h3 className="font-display font-bold text-lg mt-4 group-hover:text-cata-cyan transition-colors uppercase tracking-wide">
                {step.title}
              </h3>
              <p className="text-sm text-ink-secondary mt-2 font-body">
                {step.description}
              </p>
            </div>
          ))}
        </div>

        {/* Links row */}
        <div className="flex flex-wrap items-center gap-6 mt-12 pt-8 border-t border-border-subtle">
          <a
            href="https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/docs/Unified%20and%20Modular%20PMOVES%20UI%20Design.md"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost"
          >
            UI Design Manifesto <span>&rarr;</span>
          </a>
          <a
            href="https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVES.AI%20PLANS/CREATOR_PIPELINE.md"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost"
          >
            Pipeline Runbook <span>&rarr;</span>
          </a>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Personas Section
   ───────────────────────────────────────────────────────────────────────────── */

function PersonasSection() {
  return (
    <section className="relative py-32 px-6 lg:px-12 bg-void-soft">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-16">
          <span className="font-pixel text-[8px] text-cata-gold tracking-wider mb-4 block">
            [ AGENT PERSONAS ]
          </span>
          <h2 className="heading-display text-4xl sm:text-5xl lg:text-6xl mt-4">
            GIVE EVERY AGENT
            <br />
            <span className="text-gradient-gold">A FACE & A VIBE</span>
          </h2>
        </div>

        {/* Personas grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {personas.map((persona) => (
            <div
              key={persona.name}
              className="group card-mech p-8"
            >
              {/* Avatar */}
              <div
                className="w-20 h-20 flex items-center justify-center font-display text-3xl font-bold mb-6 transition-transform group-hover:scale-110 corner-cut"
                style={{
                  backgroundColor: `${persona.color}20`,
                  color: persona.color,
                  border: `2px solid ${persona.color}`,
                }}
              >
                {persona.initial}
              </div>

              {/* Content */}
              <div className="space-y-2">
                <h3 className="font-display font-bold text-xl group-hover:text-cata-cyan transition-colors uppercase tracking-wide">
                  {persona.name}
                </h3>
                <p className="font-pixel text-[7px] text-ink-secondary uppercase tracking-wider">
                  {persona.role}
                </p>
              </div>

              {/* Theme tag */}
              <div className="mt-6 pt-6 border-t border-border-subtle">
                <span className="font-pixel text-[6px] text-ink-muted uppercase">Theme</span>
                <p className="font-display text-sm mt-1 uppercase tracking-wide" style={{ color: persona.color }}>
                  {persona.theme}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Footer note */}
        <p className="text-center font-pixel text-[7px] text-ink-muted uppercase tracking-widest mt-12">
          Swap presets via creator pipelines // Keep voices synced with VibeVoice + RVC
        </p>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Console Section
   ───────────────────────────────────────────────────────────────────────────── */

function ConsoleSection({
  services,
  statuses,
}: {
  services: ServiceLink[];
  statuses: (boolean | undefined)[];
}) {
  return (
    <section className="relative py-32 px-6 lg:px-12">
      {/* Background */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute left-1/4 bottom-0 w-1/2 h-1/2 bg-glow-cyan opacity-10 blur-[150px]" />
      </div>

      <div className="relative max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <span className="font-pixel text-[8px] text-cata-cyan tracking-wider mb-4 block">
            [ OPERATOR CONSOLE ]
          </span>
          <h2 className="heading-display text-4xl sm:text-5xl lg:text-6xl mt-4">
            SERVICE STATUS
          </h2>
          <p className="max-w-xl mx-auto text-ink-secondary mt-6 font-body">
            Real-time health monitoring across the POWERFULMOVES infrastructure.
          </p>
        </div>

        {/* Services grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-px bg-border-subtle mb-12">
          {services.map((service, idx) => {
            const status = statuses[idx];
            const isHealthy = status === true;
            const isDown = status === false;

            return (
              <a
                key={service.label}
                href={service.href}
                target={service.href.startsWith('http') ? '_blank' : undefined}
                rel={service.href.startsWith('http') ? 'noreferrer' : undefined}
                className="bg-void p-6 hover:bg-void-elevated transition-colors group"
              >
                {/* Status indicator */}
                <div className="flex items-center justify-between mb-4">
                  <div
                    className={`w-2 h-2 ${
                      isHealthy ? 'bg-cata-forest animate-pulse' :
                      isDown ? 'bg-cata-ember' :
                      'bg-ink-muted'
                    }`}
                  />
                  {service.port && (
                    <span className="font-mono text-2xs text-ink-muted">:{service.port}</span>
                  )}
                </div>

                {/* Label */}
                <h3 className="font-display font-semibold text-xs group-hover:text-cata-cyan transition-colors uppercase tracking-wide">
                  {service.label}
                </h3>

                {/* Status badge */}
                <div className="mt-3">
                  {service.health ? (
                    <span className={`font-pixel text-[6px] uppercase ${
                      isHealthy ? 'text-cata-forest' :
                      isDown ? 'text-cata-ember' :
                      'text-ink-muted'
                    }`}>
                      {isHealthy ? 'Online' : isDown ? 'Offline' : 'Unknown'}
                    </span>
                  ) : (
                    <span className="font-pixel text-[6px] uppercase text-ink-muted">
                      Link
                    </span>
                  )}
                </div>
              </a>
            );
          })}
        </div>

        {/* CTA */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link href="/dashboard/ingest" className="btn-primary">
            Open Dashboard
          </Link>
          <Link href="/dashboard/monitor" className="btn-secondary">
            View Metrics
          </Link>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Footer
   ───────────────────────────────────────────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border-subtle py-16 px-6 lg:px-12">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between gap-12">
          {/* Brand */}
          <div className="max-w-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-6 h-6 bg-cata-cyan corner-cut" />
              <span className="font-display font-bold text-sm tracking-widest">POWERFULMOVES</span>
            </div>
            <p className="text-sm text-ink-secondary font-body">
              Local-first autonomy, reproducible provisioning, and self-improving research loops.
            </p>
            <p className="font-pixel text-[7px] text-ink-muted mt-4">
              Cataclysm Studios Inc. // {new Date().getFullYear()}
            </p>
          </div>

          {/* Links */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-8">
            <div>
              <h4 className="font-display font-semibold text-xs uppercase tracking-wider text-ink-muted mb-4">Platform</h4>
              <ul className="space-y-2">
                <li><Link href="/dashboard/ingest" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Ingestion</Link></li>
                <li><Link href="/dashboard/notebook" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Notebook</Link></li>
                <li><Link href="/dashboard/services" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Services</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-display font-semibold text-xs uppercase tracking-wider text-ink-muted mb-4">Resources</h4>
              <ul className="space-y-2">
                <li><a href="https://github.com/POWERFULMOVES/PMOVES.AI" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">GitHub</a></li>
                <li><Link href="/community" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Community</Link></li>
                <li><a href="https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/README.md" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Documentation</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-display font-semibold text-xs uppercase tracking-wider text-ink-muted mb-4">Connect</h4>
              <ul className="space-y-2">
                <li><a href="https://discord.gg/cataclysm" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Discord</a></li>
                <li><a href="https://twitter.com/cataclysm" className="text-sm text-ink-secondary hover:text-cata-cyan font-body">Twitter</a></li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-16 pt-8 border-t border-border-subtle flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <span className="w-3 h-3 bg-cata-cyan" />
            <span className="w-3 h-3 bg-cata-ember" />
            <span className="w-3 h-3 bg-cata-forest" />
            <span className="w-3 h-3 bg-cata-gold" />
          </div>
          <span className="font-pixel text-[7px] text-ink-muted uppercase">The Cataclysm palette guiding every move</span>
        </div>
      </div>
    </footer>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Main Page
   ───────────────────────────────────────────────────────────────────────────── */

export default async function HomePage() {
  const services = getServiceLinks();
  const statuses = await Promise.all(services.map((s) => probe(s.health)));

  return (
    <main className="bg-void text-ink-primary">
      <div className="noise-overlay" />
      <HeroSection />
      <ModulesSection />
      <PipelineSection />
      <PersonasSection />
      <ConsoleSection services={services} statuses={statuses} />
      <Footer />
    </main>
  );
}
