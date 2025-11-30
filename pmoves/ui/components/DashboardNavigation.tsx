"use client";

import Link from 'next/link';

const NAV_LINKS: Array<{ href: string; label: string; key: NavKey }> = [
  { href: '/dashboard/ingest', label: 'Ingestion', key: 'ingest' },
  { href: '/dashboard/videos', label: 'Video reviews', key: 'videos' },
  { href: '/dashboard/monitor', label: 'Monitor', key: 'monitor' },
  { href: '/dashboard/notebook', label: 'Notebook', key: 'notebook' },
  { href: '/dashboard/notebook/runtime', label: 'Notebook runtime', key: 'notebook-runtime' },
  { href: '/notebook-workbench', label: 'Workbench', key: 'notebook-workbench' },
  { href: '/dashboard/personas', label: 'Personas', key: 'personas' },
  { href: '/dashboard/chat', label: 'Chat', key: 'chat' },
  { href: '/dashboard/services', label: 'Services', key: 'services' },
  { href: '/dashboard/chit', label: 'Chit live', key: 'chit' },
];

export type NavKey =
  | 'ingest'
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
  active: NavKey;
}

export function DashboardNavigation({ active }: DashboardNavigationProps) {
  const singleUser =
    String(process.env.NEXT_PUBLIC_SINGLE_USER_MODE || process.env.SINGLE_USER_MODE || '1') ===
    '1';
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
      {singleUser ? (
        <span className="ml-2 rounded-full border border-emerald-500 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
          Owner mode
        </span>
      ) : null}
    </nav>
  );
}

export default DashboardNavigation;
