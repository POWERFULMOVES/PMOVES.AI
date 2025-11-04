import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { SupabaseClientBootstrap } from '@/components/SupabaseClientBootstrap';

export const metadata: Metadata = {
  title: {
    default: 'Cataclysm Studios • Community-Powered AI',
    template: '%s • Cataclysm Studios'
  },
  description:
    'Cataclysm Studios fuses PMOVES.AI technology, decentralized governance, and the DARKXSIDE creative narrative to empower communities with AI, blockchain, and collaborative creativity.',
  keywords: [
    'Cataclysm Studios',
    'PMOVES.AI',
    'DARKXSIDE',
    'community-owned AI',
    'cooperative onboarding',
    'Supabase pilot'
  ],
  category: 'technology',
  openGraph: {
    title: 'Cataclysm Studios • Community-Powered AI',
    description:
      'Cataclysm Studios fuses PMOVES.AI technology, decentralized governance, and the DARKXSIDE creative narrative to empower communities with AI, blockchain, and collaborative creativity.',
    type: 'website'
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Cataclysm Studios • Community-Powered AI',
    description:
      'Cataclysm Studios fuses PMOVES.AI technology, decentralized governance, and the DARKXSIDE creative narrative to empower communities with AI, blockchain, and collaborative creativity.'
  }
};

export default function MarketingLayout({
  children
}: {
  children: ReactNode;
}) {
  const currentYear = new Date().getFullYear();

  return (
    <div className="relative min-h-screen bg-brand-ink-strong text-brand-inverse">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,var(--color-brand-sky)/0.2,transparent_55%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,var(--color-brand-gold)/0.18,transparent_60%)]" />
      </div>
      <SupabaseClientBootstrap />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-10 lg:px-10">
        <header className="flex flex-col gap-4 pb-10 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="text-base font-semibold text-brand-gold transition hover:text-brand-sky">
            Cataclysm Studios
          </Link>
          <nav className="flex flex-wrap items-center gap-4 text-sm font-medium text-brand-subtle">
            <Link href="/community" className="transition hover:text-brand-inverse">
              Community
            </Link>
            <Link href="/dashboard/ingest" className="transition hover:text-brand-inverse">
              Operator Console
            </Link>
            <Link href="/login" className="transition hover:text-brand-inverse">
              Sign in
            </Link>
            <a
              href="https://supabase.com/dashboard/sign-up"
              className="transition hover:text-brand-inverse"
              target="_blank"
              rel="noreferrer"
            >
              Supabase onboarding
            </a>
          </nav>
        </header>
        <main className="flex-1 pb-16">{children}</main>
        <footer className="border-t border-brand-border pt-8 text-xs text-brand-subtle">
          <p>© {currentYear} Cataclysm Studios Inc. Community-powered AI with PMOVES.AI.</p>
        </footer>
      </div>
    </div>
  );
}
