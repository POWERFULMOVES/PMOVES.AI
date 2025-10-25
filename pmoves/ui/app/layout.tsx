import './globals.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'PMOVES Ingestion',
  description: 'Upload and track creative assets.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-100 text-slate-900">{children}</body>
    </html>
  );
}
