import type { Metadata, Viewport } from 'next';
import './globals.css';

/* ═══════════════════════════════════════════════════════════════════════════
   PMOVES.AI Root Layout — Cymatic Neo-Brutalism
   Cataclysm Studios Inc.
   ═══════════════════════════════════════════════════════════════════════════ */

export const metadata: Metadata = {
  title: {
    default: 'PMOVES.AI — Powerful Moves for Everyday Creators',
    template: '%s | PMOVES.AI',
  },
  description: '60+ microservice orchestration platform featuring autonomous agents, hybrid RAG, and multimodal deep research. From cymatic storyweaving to geometry bus coordination.',
  keywords: ['AI', 'orchestration', 'agents', 'RAG', 'multimodal', 'research', 'Cataclysm Studios'],
  authors: [{ name: 'Cataclysm Studios Inc.' }],
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://pmoves.ai',
    siteName: 'PMOVES.AI',
    title: 'PMOVES.AI — Powerful Moves for Everyday Creators',
    description: '60+ microservice orchestration platform featuring autonomous agents, hybrid RAG, and multimodal deep research.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'PMOVES.AI',
    description: 'Powerful Moves for Everyday Creators',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#050508',
  colorScheme: 'dark',
};

export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        {/* Preconnect to Google Fonts */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="min-h-screen bg-void text-ink-primary antialiased">
        {children}
      </body>
    </html>
  );
}
