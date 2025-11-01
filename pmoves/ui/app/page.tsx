import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="cataclysm-gradient relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-20 text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 opacity-60 blur-3xl" aria-hidden>
          <div className="absolute left-1/4 top-10 h-72 w-72 rounded-full bg-[var(--cataclysm-horizon)]/40 mix-blend-screen" />
          <div className="absolute right-1/5 top-1/3 h-96 w-96 rounded-full bg-[var(--cataclysm-forest)]/30 mix-blend-screen" />
          <div className="absolute left-1/2 bottom-10 h-80 w-80 rounded-full bg-[var(--cataclysm-ember)]/25 mix-blend-screen" />
        </div>
        <div className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-[var(--cataclysm-gold)]/10 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(31,184,205,0.12),rgba(10,10,20,0.9))]" aria-hidden />
        <div className="absolute inset-0 opacity-30" aria-hidden>
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
            PMOVES is the confident pulse behind modern creator cooperatives—equipping every contributor with the same precision
            tooling, knowledge routing, and expressive surfaces the studio team uses to ship breakthroughs together.
          </p>
          <p className="mx-auto max-w-2xl text-sm text-slate-300 sm:text-lg">
            Plug into the <span className="text-[var(--cataclysm-cyan)]">Powerful Moves</span> community to co-design workflows, or
            step into the engineer console for authenticated access to Supabase-powered operations. Whatever your lane, the
            network is ready to move in sync with you.
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

        <p className="text-xs uppercase tracking-[0.3em] text-[var(--cataclysm-slate)]">
          Cyan · Ember · Forest · Gold — the Cataclysm palette guiding every move.
        </p>
      </div>
    </main>
  );
}
