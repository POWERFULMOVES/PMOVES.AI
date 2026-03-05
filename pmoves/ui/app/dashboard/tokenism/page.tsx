import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

export const metadata: Metadata = {
  title: 'Tokenism | PMOVES',
  description: 'Token economy simulation and operational docs',
};

export default function TokenismPage() {
  redirect('/dashboard/services/tokenism');
}
