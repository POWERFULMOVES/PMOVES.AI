import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PMOVES Console',
  description: 'Secure operator console for PMOVES ingestion workflows.',
};

export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="bg-brand-surface">
      <body className="min-h-screen bg-brand-surface text-brand-ink antialiased">{children}</body>
    </html>
  );
}
