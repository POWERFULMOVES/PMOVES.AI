import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-brand-surface p-8 text-center">
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold text-brand-ink">PMOVES Operator Console</h1>
        <p className="max-w-md text-sm text-brand-muted">
          Sign in to manage ingestion workflows, upload new assets, and monitor Supabase processing pipelines.
        </p>
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-6 py-20 text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 opacity-60 blur-3xl" aria-hidden>
          <div className="absolute left-1/4 top-10 h-72 w-72 rounded-full bg-[var(--cataclysm-cyan)]/40 mix-blend-screen" />
          <div className="absolute right-1/5 top-1/3 h-96 w-96 rounded-full bg-[var(--cataclysm-forest)]/30 mix-blend-screen" />
          <div className="absolute left-1/2 bottom-10 h-80 w-80 rounded-full bg-[var(--cataclysm-ember)]/25 mix-blend-screen" />
        </div>
        <div className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-[var(--cataclysm-gold)]/10 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(31,184,205,0.12),rgba(10,10,20,0.9))]" aria-hidden />
        <div className="absolute inset-0 opacity-40" aria-hidden>
          <svg className="h-full w-full" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="grid" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(210,186,76,0.25)" />
                <stop offset="100%" stopColor="rgba(31,184,205,0.15)" />
              </linearGradient>
            </defs>
            <path
              d="M0 100 Q150 120 300 100 T600 100"
              stroke="rgba(45,197,253,0.2)"
              strokeWidth="0.5"
            />
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
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href="/login"
          className="rounded bg-brand-sky px-5 py-2 text-sm font-semibold text-brand-ink-strong shadow hover:bg-brand-gold"
        >
          Continue to login
        </Link>
        <Link
          href="/dashboard/ingest"
          className="rounded border border-brand-border px-5 py-2 text-sm font-semibold text-brand-ink hover:border-brand-slate hover:text-brand-ink-strong"
        >
          View ingestion dashboard
        </Link>
        <Link
          href="/community"
          className="rounded border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400 hover:text-slate-900"
        >
          Explore the community vision
        </Link>

      <div className="relative z-10 flex w-full max-w-5xl flex-col items-center gap-16 text-center">
        <div className="space-y-6">
          <span className="inline-flex items-center justify-center rounded-full border border-white/20 bg-white/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.32em] text-[var(--cataclysm-gold)]">
            Cataclysm Studios Inc. presents
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl">
            Powerful Moves for everyday creators
          </h1>
          <p className="mx-auto max-w-3xl text-base text-slate-200 sm:text-xl">
            From <strong className="text-[var(--cataclysm-cyan)]">CATACLYSM STUDIOS INC.</strong> and the POWERFULMOVES initiative comes a symphony of
            cymatics, holography, and precision geometry. PMOVES orchestrates the Chit System, Geometry Bus, and cooperative
            automations so collectives can prototype, publish, and scale together.
          </p>
          <p className="mx-auto max-w-2xl text-sm text-slate-300 sm:text-lg">
            Explore <strong className="text-[var(--cataclysm-gold)]">PMOVES.AI</strong> for the full capability atlas, tap into <strong className="text-[var(--cataclysm-forest)]">cataclsmtudios.com</strong>
            for the studio constellation, and connect via the Cataclysm home lab network spanning cataclsysmstudios.net.
          </p>
        </div>

        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/community"
            className="inline-flex items-center justify-center rounded-full bg-[var(--cataclysm-cyan)] px-8 py-3 text-sm font-semibold uppercase tracking-wide text-white shadow-[0_20px_45px_-20px_rgba(31,184,205,0.8)] transition duration-200 ease-out hover:scale-[1.02] hover:bg-[var(--cataclysm-forest)] hover:shadow-[0_25px_50px_-20px_rgba(46,139,87,0.9)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cataclysm-gold)] focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            Enter community onboarding
          </Link>
          <Link
            href="/login?next=%2Fdashboard%2Fingest"
            className="inline-flex items-center justify-center rounded-full bg-[var(--cataclysm-ember)] px-8 py-3 text-sm font-semibold uppercase tracking-wide text-white shadow-[0_20px_45px_-20px_rgba(219,69,69,0.8)] transition duration-200 ease-out hover:scale-[1.02] hover:bg-[var(--cataclysm-gold)] hover:text-slate-900 hover:shadow-[0_25px_50px_-20px_rgba(210,186,76,0.95)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cataclysm-cyan)] focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            Launch engineer console
          </Link>
        </div>

        <div className="grid w-full gap-6 text-left sm:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-[rgba(31,184,205,0.15)] backdrop-blur">
            <h2 className="text-lg font-semibold text-[var(--cataclysm-cyan)]">Cymatic Storyweaving</h2>
            <p className="mt-3 text-sm text-slate-200">
              Visualize resonance: sound-reactive plots show how data pulses across PMOVES, making invisible flows tangible for
              every collaborator.
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-[rgba(210,186,76,0.15)] backdrop-blur">
            <h2 className="text-lg font-semibold text-[var(--cataclysm-gold)]">Geometry Bus</h2>
            <p className="mt-3 text-sm text-slate-200">
              Align holographic schemas, blueprint automations, and choreograph supply chains with the geometry-first logic core
              of PMOVES.
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-[rgba(219,69,69,0.15)] backdrop-blur">
            <h2 className="text-lg font-semibold text-[var(--cataclysm-ember)]">Chit System</h2>
            <p className="mt-3 text-sm text-slate-200">
              Tokenize commitments, route resources, and surface accountability loops that let communities move with precision and
              care.
            </p>
          </div>
        </div>

        <p className="text-xs uppercase tracking-[0.3em] text-[var(--cataclysm-slate)]">
          Cataclysm palette: cyan · ember · forest · gold — engineered for luminous collaboration.
        </p>
      </div>
    </main>
  );
}
