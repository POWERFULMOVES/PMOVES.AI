import Link from 'next/link';
import { SystemHubSection } from '@/components/hub/SystemHubSection';

/* ═══════════════════════════════════════════════════════════════════════════
   POWERFULMOVES Landing Page — Megaman × Transformers
   Cataclysm Studios Inc.
   ═══════════════════════════════════════════════════════════════════════════ */

type PipelineStep = {
  num: string;
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

const pipeline: PipelineStep[] = [
  { num: '01', title: 'Create', description: 'ComfyUI renders assets and pushes to MinIO' },
  { num: '02', title: 'Webhook', description: 'Render webhook stamps studio_board rows' },
  { num: '03', title: 'Approve', description: 'Operators triage in Studio Board' },
  { num: '04', title: 'Publish', description: 'Emit to Discord, Jellyfin, Geometry Bus' },
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

/* ─────────────────────────────────────────────────────────────────────────────
   Hero Section — Megaman × Transformers Style
   ───────────────────────────────────────────────────────────────────────────── */

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

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <SystemHubSection />
      <PipelineSection />
      <PersonasSection />
      <Footer />
    </main>
  );
}
