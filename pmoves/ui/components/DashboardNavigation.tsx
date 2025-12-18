"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';

/* ═══════════════════════════════════════════════════════════════════════════
   Dashboard Navigation — Cymatic Neo-Brutalism
   ═══════════════════════════════════════════════════════════════════════════ */

type NavItem = {
  href: string;
  label: string;
  key: NavKey;
  accent?: 'cyan' | 'ember' | 'forest' | 'gold' | 'violet';
};

const NAV_ITEMS: NavItem[] = [
  { href: '/dashboard/ingest', label: 'Ingestion', key: 'ingest', accent: 'cyan' },
  { href: '/dashboard/ingestion-queue', label: 'Queue', key: 'ingestion-queue' },
  { href: '/dashboard/videos', label: 'Videos', key: 'videos', accent: 'ember' },
  { href: '/dashboard/monitor', label: 'Monitor', key: 'monitor', accent: 'forest' },
  { href: '/dashboard/notebook', label: 'Notebook', key: 'notebook', accent: 'violet' },
  { href: '/dashboard/notebook/runtime', label: 'Runtime', key: 'notebook-runtime' },
  { href: '/notebook-workbench', label: 'Workbench', key: 'notebook-workbench' },
  { href: '/dashboard/personas', label: 'Personas', key: 'personas', accent: 'gold' },
  { href: '/dashboard/chat', label: 'Chat', key: 'chat' },
  { href: '/dashboard/services', label: 'Services', key: 'services' },
  { href: '/dashboard/chit', label: 'Chit', key: 'chit', accent: 'cyan' },
];

export type NavKey =
  | 'ingest'
  | 'ingestion-queue'
  | 'videos'
  | 'monitor'
  | 'notebook'
  | 'notebook-runtime'
  | 'notebook-workbench'
  | 'personas'
  | 'chat'
  | 'services'
  | 'chit';

interface DashboardNavigationProps {
  active?: NavKey;
}

const accentColors: Record<string, string> = {
  cyan: 'border-cata-cyan text-cata-cyan bg-cata-cyan/10',
  ember: 'border-cata-ember text-cata-ember bg-cata-ember/10',
  forest: 'border-cata-forest text-cata-forest bg-cata-forest/10',
  gold: 'border-cata-gold text-cata-gold bg-cata-gold/10',
  violet: 'border-cata-violet text-cata-violet bg-cata-violet/10',
};

export function DashboardNavigation({ active }: DashboardNavigationProps) {
  const pathname = usePathname();
  const singleUser =
    String(process.env.NEXT_PUBLIC_SINGLE_USER_MODE || process.env.SINGLE_USER_MODE || '1') === '1';

  return (
    <nav className="flex flex-wrap items-center gap-2">
      {NAV_ITEMS.map((item) => {
        const isActive = item.key === active || pathname === item.href;
        const accent = item.accent ? accentColors[item.accent] : '';

        return (
          <Link
            key={item.key}
            href={item.href}
            className={`
              relative px-3 py-1.5 text-xs font-mono uppercase tracking-wider
              border transition-all duration-200
              ${isActive
                ? accent || 'border-ink-primary text-ink-primary bg-ink-primary/10'
                : 'border-border-subtle text-ink-secondary hover:border-ink-muted hover:text-ink-primary'
              }
            `}
          >
            {item.label}
            {isActive && (
              <span className="absolute -bottom-px left-1/2 -translate-x-1/2 w-4 h-px bg-current" />
            )}
          </Link>
        );
      })}

      {singleUser && (
        <span className="ml-3 px-2 py-1 text-2xs font-mono uppercase tracking-wider text-cata-forest border border-cata-forest bg-cata-forest/10">
          Owner
        </span>
      )}
    </nav>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Dashboard Header Component
   ───────────────────────────────────────────────────────────────────────────── */

interface DashboardHeaderProps {
  title: string;
  subtitle?: string;
  active?: NavKey;
  actions?: React.ReactNode;
}

export function DashboardHeader({ title, subtitle, active, actions }: DashboardHeaderProps) {
  return (
    <header className="border-b border-border-subtle bg-void-elevated">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-6 h-6 bg-cata-cyan group-hover:bg-cata-forest transition-colors" />
          <span className="font-display font-bold text-sm tracking-wide">PMOVES.AI</span>
        </Link>

        <div className="flex items-center gap-4">
          {actions}
          <Link href="/dashboard/services" className="btn-ghost text-xs">
            All Services
          </Link>
        </div>
      </div>

      {/* Navigation */}
      <div className="px-6 py-3 overflow-x-auto">
        <DashboardNavigation active={active} />
      </div>

      {/* Page title */}
      <div className="px-6 py-6">
        <h1 className="font-display font-bold text-2xl">{title}</h1>
        {subtitle && (
          <p className="text-sm text-ink-secondary mt-1">{subtitle}</p>
        )}
      </div>
    </header>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Dashboard Shell Component
   ───────────────────────────────────────────────────────────────────────────── */

interface DashboardShellProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  active?: NavKey;
  actions?: React.ReactNode;
}

export function DashboardShell({ children, title, subtitle, active, actions }: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-void text-ink-primary">
      <div className="noise-overlay" />
      <DashboardHeader title={title} subtitle={subtitle} active={active} actions={actions} />
      {/* Target for skip link in layout.tsx - WCAG 2.1 SC 2.4.1 */}
      <main id="main-content" tabIndex={-1} className="relative">
        {children}
      </main>
    </div>
  );
}

export default DashboardNavigation;
