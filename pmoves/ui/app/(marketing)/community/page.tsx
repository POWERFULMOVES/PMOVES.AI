import Link from 'next/link';

const ctaLinks = [
  {
    label: 'Launch the Supabase pilot',
    href: 'https://supabase.com/dashboard/sign-up',
    description:
      'Provision your workspace with the same Supabase backbone that powers PMOVES ingestion, approvals, and cooperative dashboards.'
  },
  {
    label: 'Read the Cataclysm brand deck',
    href: 'https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md',
    description:
      'Dive deeper into the narrative that connects Cataclysm Studios, PMOVES.AI, and the DARKXSIDE creative movement.'
  }
];

export default function CommunityPage() {
  return (
    <section className="space-y-16">
      <div className="rounded-3xl border border-brand-border bg-[rgba(5,15,17,0.65)] p-10 shadow-2xl backdrop-blur">
        <p className="text-xs uppercase tracking-[0.3em] text-brand-subtle">Community-first launchpad</p>
        <h1 className="mt-4 text-4xl font-semibold text-brand-crimson sm:text-5xl">
          Empower neighbors with cooperative AI
        </h1>
        <p className="mt-6 max-w-3xl text-base leading-relaxed text-brand-inverse">
          Cataclysm Studios merges advanced AI, blockchain-powered governance, and DARKXSIDE’s creative storytelling so local teams
          can organize, produce, and thrive together. PMOVES.AI is the technical core of that movement—coordinating multi-agent
          workflows while keeping data grounded in the communities that generate it.
        </p>
        <div className="mt-8 flex flex-col gap-4 sm:flex-row">
          {ctaLinks.map((cta) => (
            <Link
              key={cta.href}
              href={cta.href}
              className="flex-1 rounded-xl border border-brand-border bg-[rgba(5,15,17,0.55)] px-6 py-5 text-left text-sm text-brand-inverse transition hover:border-brand-crimson hover:bg-[rgba(5,15,17,0.75)]"
              target={cta.href.startsWith('http') ? '_blank' : undefined}
              rel={cta.href.startsWith('http') ? 'noreferrer' : undefined}
            >
              <span className="block text-sm font-semibold text-brand-inverse">{cta.label}</span>
              <span className="mt-2 block text-xs text-brand-subtle">{cta.description}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-3xl border border-brand-border bg-[rgba(5,15,17,0.55)] p-8">
          <h2 className="text-2xl font-semibold text-brand-inverse">Why the community matters</h2>
          <p className="mt-4 text-sm leading-relaxed text-brand-subtle">
            Cataclysm Studios Inc. exists to catalyze equitable, creative economies by pairing the PMOVES.AI engine with DARKXSIDE’s
            cultural storytelling. Together they turn fragmented local efforts into resilient ecosystems where everyone can be a
            stakeholder, creator, and decision-maker.
          </p>
          <ul className="mt-6 space-y-4 text-sm text-brand-inverse">
            <li className="flex gap-3">
              <span className="mt-1 h-2 w-2 rounded-full" style={{ backgroundColor: 'var(--color-brand-sky)' }} />
              <span>
                PMOVES.AI orchestrates modular agents across cloud and local hardware so neighborhoods can automate workflows while
                owning their data end to end.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="mt-1 h-2 w-2 rounded-full" style={{ backgroundColor: '#7c3aed' }} />
              <span>
                DARKXSIDE frames the cultural narrative, translating technical breakthroughs into art, music, and stories that build
                trust and momentum.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="mt-1 h-2 w-2 rounded-full" style={{ backgroundColor: 'var(--color-brand-crimson)' }} />
              <span>
                Cataclysm’s DAO tooling and cooperative finance patterns invite residents, creators, and partners to co-govern every
                pilot from day one.
              </span>
            </li>
          </ul>
        </div>

        <aside className="flex flex-col justify-between gap-6 rounded-3xl border border-brand-border bg-[rgba(5,15,17,0.7)] p-8">
          <div>
            <h3 className="text-lg font-semibold text-brand-inverse">Built on Supabase</h3>
            <p className="mt-3 text-sm text-brand-subtle">
              Supabase stores the unified knowledge base for PMOVES, making it seamless to capture media insights, cooperative votes,
              and operational telemetry without leaving the open-source stack.
            </p>
          </div>
          <div
            className="rounded-2xl border border-brand-crimson bg-[rgba(5,11,26,0.85)] p-5 text-sm text-brand-inverse"
          >
            <p className="text-xs uppercase tracking-wide text-brand-subtle">Coming next</p>
            <p className="mt-2 text-sm">
              Join the pilot cohort to help script new cooperative economies—from Bronx food hubs to distributed creator guilds.
            </p>
          </div>
        </aside>
      </div>
    </section>
  );
}
