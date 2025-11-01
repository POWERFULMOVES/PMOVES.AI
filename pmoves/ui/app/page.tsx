import Link from 'next/link';

const featureHighlights = [
  {
    title: 'Cymatic Storyweaving',
    description:
      'Visualize resonance and trace how data pulses through PMOVES. Every collaborator can see the flows that keep the collective in sync.',
    accentClass: 'text-brand-sky',
    shadow: 'shadow-[0_18px_42px_-22px_rgba(31,184,205,0.65)]',
  },
  {
    title: 'Geometry Bus',
    description:
      'Align holographic schemas, choreograph automations, and keep publishing pipelines aligned with the geometry-first logic core.',
    accentClass: 'text-brand-gold',
    shadow: 'shadow-[0_18px_42px_-22px_rgba(210,186,76,0.6)]',
  },
  {
    title: 'Chit System',
    description:
      'Tokenize commitments, route resources, and surface accountability loops so communities can move with precision and care.',
    accentClass: 'text-brand-crimson',
    shadow: 'shadow-[0_18px_42px_-22px_rgba(180,65,60,0.6)]',
  },
] as const;

export default function HomePage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center overflow-hidden bg-brand-surface text-brand-ink">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,var(--color-brand-sky)/0.15,transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,var(--color-brand-gold)/0.12,transparent_65%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,transparent,var(--color-brand-sky)/0.08_45%,transparent_65%)]" />
      </div>

      <div className="relative z-10 flex w-full max-w-5xl flex-1 flex-col items-center gap-20 px-6 py-20 text-center lg:px-10">
        <header className="space-y-6">
          <span className="inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-inverse/80 px-4 py-1 text-xs font-semibold uppercase tracking-[0.32em] text-brand-gold">
            Powered by Cataclysm Studios
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-brand-ink-strong sm:text-6xl">
            PMOVES Operator Console
          </h1>
          <p className="mx-auto max-w-3xl text-base text-brand-muted sm:text-xl">
            Manage ingestion workflows, upload new assets, and monitor Supabase processing pipelines with a palette tuned to the
            PMOVES brand.
          </p>
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-full bg-brand-sky px-6 py-2 text-sm font-semibold text-brand-ink-strong shadow-[0_16px_36px_-20px_rgba(31,184,205,0.85)] transition hover:bg-brand-gold hover:text-brand-ink-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 focus-visible:ring-offset-brand-inverse"
            >
              Continue to login
            </Link>
            <Link
              href="/dashboard/ingest"
              className="inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-inverse px-6 py-2 text-sm font-semibold text-brand-ink transition hover:border-brand-slate hover:text-brand-ink-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-slate focus-visible:ring-offset-2 focus-visible:ring-offset-brand-inverse"
            >
              View ingestion dashboard
            </Link>
            <Link
              href="/community"
              className="inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-surface-muted px-6 py-2 text-sm font-semibold text-brand-muted transition hover:bg-brand-inverse hover:text-brand-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-muted focus-visible:ring-offset-2 focus-visible:ring-offset-brand-inverse"
            >
              Explore the community vision
            </Link>
          </div>
        </header>

        <section className="grid w-full gap-6 text-left sm:grid-cols-3">
          {featureHighlights.map((feature) => (
            <article
              key={feature.title}
              className={`rounded-3xl border border-brand-border bg-brand-inverse/90 p-6 ${feature.shadow}`}
            >
              <h2 className={`text-lg font-semibold ${feature.accentClass}`}>{feature.title}</h2>
              <p className="mt-3 text-sm text-brand-ink">{feature.description}</p>
            </article>
          ))}
        </section>

        <p className="text-xs uppercase tracking-[0.3em] text-brand-subtle">
          Cyan · Crimson · Forest · Slate · Gold · Rust — the PMOVES palette for cooperative action.
        </p>
      </div>
    </main>
  );
}
