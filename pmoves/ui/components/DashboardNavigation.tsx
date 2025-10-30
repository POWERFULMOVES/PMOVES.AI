"use client";

import Link from 'next/link';

const NAV_LINKS: Array<{ href: string; label: string; key: NavKey }> = [
  { href: '/dashboard/ingest', label: 'Ingestion', key: 'ingest' },
  { href: '/dashboard/videos', label: 'Video reviews', key: 'videos' },
  { href: '/dashboard/services', label: 'Services', key: 'services' },
];

export type NavKey = 'ingest' | 'videos' | 'services';

interface DashboardNavigationProps {
  active: NavKey;
}

export function DashboardNavigation({ active }: DashboardNavigationProps) {
  return (
    <nav className="flex flex-wrap items-center gap-2">
      {NAV_LINKS.map((link) => {
        const isActive = link.key === active;
        return (
          <Link
            key={link.key}
            href={link.href}
            className={`rounded-full border px-3 py-1 text-sm font-medium transition-colors ${
              isActive
                ? 'border-slate-900 bg-slate-900 text-white shadow-sm'
                : 'border-slate-300 text-slate-600 hover:border-slate-400 hover:text-slate-900'
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default DashboardNavigation;
