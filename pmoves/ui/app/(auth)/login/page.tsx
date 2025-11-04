import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { featureFlags } from '@/config/featureFlags';
import { getEnabledAuthProviders } from '@/config/supabaseProviders';
import { LoginForm } from './LoginForm';

export const dynamic = 'force-dynamic';

type LoginPageSearchParams = Record<string, string | string[] | undefined>;

const sanitizeNextParam = (value: string | string[] | undefined): string | undefined => {
  if (Array.isArray(value)) {
    return sanitizeNextParam(value[0]);
  }
  if (!value) return undefined;
  if (!value.startsWith('/')) {
    return undefined;
  }
  return value;
};

const sanitizeErrorParam = (value: string | string[] | undefined): string | undefined => {
  if (Array.isArray(value)) {
    return sanitizeErrorParam(value[0]);
  }
  if (!value) return undefined;
  return value;
};

const callbackUrl = process.env.NEXT_PUBLIC_SUPABASE_AUTH_CALLBACK_URL ?? '/callback';

export const metadata: Metadata = {
  title: 'Sign in • PMOVES',
  description: 'Authenticate with Supabase to access the PMOVES operator console.'
};

export default function LoginPage({
  searchParams
}: {
  searchParams?: LoginPageSearchParams;
}) {
  if (!featureFlags.passwordAuth && !featureFlags.oauth) {
    notFound();
  }

  const nextParam = sanitizeNextParam(searchParams?.next);
  const initialError = sanitizeErrorParam(searchParams?.error);
  const providers = featureFlags.oauth ? getEnabledAuthProviders() : [];

  return (
    <main className="flex min-h-screen items-center justify-center bg-brand-surface px-6 py-16 text-brand-ink">
      <section className="flex w-full max-w-4xl flex-col gap-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold text-brand-ink-strong sm:text-4xl">Welcome back</h1>
          <p className="text-sm text-brand-muted">
            Use your PMOVES Supabase credentials or a supported social provider to continue.
          </p>
        </header>

        <div className="flex flex-wrap gap-6">
          <div className="flex min-w-[280px] flex-1">
            <LoginForm
              providers={providers}
              passwordEnabled={featureFlags.passwordAuth}
              callbackUrl={callbackUrl}
              nextPath={nextParam}
              initialError={initialError ?? null}
            />
          </div>

          <aside className="flex min-w-[240px] flex-1 flex-col gap-4 rounded-2xl border border-brand-border bg-[rgba(16,43,47,0.1)] p-6 text-sm text-brand-ink">
            <h2 className="text-lg font-semibold text-brand-ink">Having trouble?</h2>
            <ul className="list-disc space-y-2 pl-5 text-brand-muted">
              <li>Confirm you are on the approved redirect host defined in Supabase.</li>
              <li>Use the password reset flow in Supabase Studio if you have forgotten your credentials.</li>
              <li>Reach out in #ops with the request ID shown in failed login toast messages.</li>
            </ul>
          </aside>
        </div>
      </section>
    </main>
  );
}
