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

type LoginPageSearchParamsInput =
  | LoginPageSearchParams
  | Promise<LoginPageSearchParams>
  | undefined;

export default async function LoginPage({
  searchParams
}: {
  searchParams?: LoginPageSearchParamsInput;
}) {
  if (!featureFlags.passwordAuth && !featureFlags.oauth) {
    notFound();
  }

  const resolvedSearchParams =
    searchParams && typeof (searchParams as Promise<LoginPageSearchParams>).then === 'function'
      ? await (searchParams as Promise<LoginPageSearchParams>)
      : (searchParams as LoginPageSearchParams | undefined);

  const nextParam = sanitizeNextParam(resolvedSearchParams?.next);
  const initialError = sanitizeErrorParam(resolvedSearchParams?.error);
  const providers = featureFlags.oauth ? getEnabledAuthProviders() : [];

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '4rem 1.5rem'
      }}
    >
      <section
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '1.5rem',
          width: '100%',
          maxWidth: '960px'
        }}
      >
        <header>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>Welcome back</h1>
          <p style={{ opacity: 0.8 }}>
            Use your PMOVES Supabase credentials or a supported social provider to continue.
          </p>
        </header>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem' }}>
          <div style={{ flex: '1 1 320px' }}>
            <LoginForm
              providers={providers}
              passwordEnabled={featureFlags.passwordAuth}
              callbackUrl={callbackUrl}
              nextPath={nextParam}
              initialError={initialError ?? null}
            />
          </div>

          <aside
            style={{
              flex: '1 1 280px',
              background: 'rgba(15, 23, 42, 0.65)',
              border: '1px solid rgba(148, 163, 184, 0.25)',
              borderRadius: '1rem',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem'
            }}
          >
            <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Having trouble?</h2>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
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
