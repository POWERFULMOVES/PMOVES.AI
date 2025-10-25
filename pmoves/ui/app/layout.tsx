import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PMOVES Console',
  description: 'PMOVES operator console authentication gateway'
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
