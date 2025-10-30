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
    <div className="bg-cataclysm-void cataclysm-gradient text-slate-100">
      <SupabaseClientBootstrap />
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-10 lg:px-10">
        <header className="flex flex-col gap-4 pb-10 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="text-base font-semibold text-cataclysm-ember">
            Cataclysm Studios
          </Link>
          <nav className="flex flex-wrap items-center gap-4 text-sm font-medium text-slate-200">
            <Link href="/community" className="transition hover:text-cataclysm-ember">
              Community
            </Link>
            <Link href="/dashboard/ingest" className="transition hover:text-cataclysm-ember">
              Operator Console
            </Link>
            <Link href="/login" className="transition hover:text-cataclysm-ember">
              Sign in
            </Link>
            <a
              href="https://supabase.com/dashboard/sign-up"
              className="transition hover:text-cataclysm-ember"
              target="_blank"
              rel="noreferrer"
            >
              Supabase onboarding
            </a>
          </nav>
        </header>
        <main className="flex-1 pb-16">{children}</main>
        <footer className="border-t border-white/10 pt-8 text-xs text-slate-400">
          <p>© {currentYear} Cataclysm Studios Inc. Community-powered AI with PMOVES.AI.</p>
        </footer>
      </div>
    </div>
  );
}
