import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import { featureFlags } from '@/config/featureFlags';
import { getEnabledAuthProviders } from '@/config/supabaseProviders';
import { loadRoom } from '@/lib/rooms';
import { LoginForm } from './LoginForm';

export const dynamic = 'force-dynamic';

type LoginPageSearchParams = Record<string, string | string[] | undefined>;

const sanitizeNextParam = (value: string | string[] | undefined): string | undefined => {
  if (Array.isArray(value)) return sanitizeNextParam(value[0]);
  if (!value) return undefined;
  if (!value.startsWith('/')) return undefined;
  return value;
};

const sanitizeErrorParam = (value: string | string[] | undefined): string | undefined => {
  if (Array.isArray(value)) return sanitizeErrorParam(value[0]);
  if (!value) return undefined;
  return value;
};

const sanitizeRoomParam = (value: string | string[] | undefined): string | undefined => {
  if (Array.isArray(value)) return sanitizeRoomParam(value[0]);
  if (!value) return undefined;
  if (!/^[a-z0-9][a-z0-9._-]*$/.test(value)) return undefined;
  return value;
};

const callbackUrl = process.env.NEXT_PUBLIC_SUPABASE_AUTH_CALLBACK_URL ?? '/callback';

export const metadata: Metadata = {
  title: 'Sign in',
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
  const roomParam = sanitizeRoomParam(resolvedSearchParams?.room_id);
  const initialError = sanitizeErrorParam(resolvedSearchParams?.error);
  const providers = featureFlags.oauth ? getEnabledAuthProviders() : [];
  const selectedRoom = roomParam ? await loadRoom(roomParam) : null;
  const resolvedNextPath = nextParam ?? selectedRoom?.manifest.shell.layout.default_route ?? '/dashboard/ingest';

  const bootJwt =
    process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT;

  if (bootJwt) {
    redirect(resolvedNextPath);
  }

  return (
    <main className="relative min-h-screen flex items-center justify-center bg-void text-ink-primary px-6 py-16 overflow-hidden">
      <div className="cymatic-grid" />
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-cata-cyan/10 blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-cata-violet/10 blur-[100px]" />
      </div>
      <div className="noise-overlay" />

      <section className="relative z-10 flex w-full max-w-5xl flex-col lg:flex-row gap-12">
        <div className="flex-1 flex flex-col justify-center">
          <Link href="/" className="flex items-center gap-3 mb-12 group">
            <div className="w-10 h-10 bg-cata-cyan group-hover:bg-cata-forest transition-colors" />
            <span className="font-display font-bold text-lg tracking-wide">PMOVES.AI</span>
          </Link>

          <h1 className="heading-display text-4xl sm:text-5xl lg:text-6xl">
            Welcome
            <br />
            <span className="heading-serif text-ink-secondary">back</span>
          </h1>

          <p className="mt-6 text-ink-secondary max-w-md">
            Use your PMOVES Supabase credentials or a supported social provider to continue to the operator console.
          </p>

          {selectedRoom && (
            <div className="mt-8 border border-cata-cyan/30 bg-void-elevated/80 p-4">
              <div className="font-pixel text-[7px] uppercase tracking-[0.18em] text-cata-cyan">Room target</div>
              <h2 className="mt-2 font-display text-xl font-bold text-ink-primary">{selectedRoom.display_name}</h2>
              <p className="mt-2 text-sm text-ink-secondary">
                {selectedRoom.summary ?? selectedRoom.manifest.description ?? 'Room manifest loaded from the PMOVES catalog.'}
              </p>
              <div className="mt-3 font-mono text-xs text-ink-muted">Entry route: {resolvedNextPath}</div>
            </div>
          )}

          <div className="mt-12 space-y-4">
            <h2 className="font-display font-semibold text-sm uppercase tracking-wider text-ink-muted">
              Having trouble?
            </h2>
            <ul className="space-y-2 text-sm text-ink-secondary">
              <li className="flex items-start gap-2">
                <span className="text-cata-cyan mt-0.5">&bull;</span>
                Confirm you are on the approved redirect host defined in Supabase.
              </li>
              <li className="flex items-start gap-2">
                <span className="text-cata-cyan mt-0.5">&bull;</span>
                Use the password reset flow in Supabase Studio if you forgot credentials.
              </li>
              <li className="flex items-start gap-2">
                <span className="text-cata-cyan mt-0.5">&bull;</span>
                Reach out in #ops with the request ID from failed login messages.
              </li>
            </ul>
          </div>
        </div>

        <div className="flex-1 flex items-center justify-center lg:justify-end">
          <LoginForm
            providers={providers}
            passwordEnabled={featureFlags.passwordAuth}
            callbackUrl={callbackUrl}
            nextPath={resolvedNextPath}
            initialError={initialError ?? null}
          />
        </div>
      </section>
    </main>
  );
}
