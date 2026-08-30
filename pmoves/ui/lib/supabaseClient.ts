import { createClient, type SupabaseClient, type Session } from '@supabase/supabase-js';
import type { Database } from './database.types';
import { logError } from './errorUtils';
import { ErrorIds } from './constants/errorIds';

type SupabaseClientOptions = {
  serviceRole?: boolean;
};

// During `next build` (e.g. inside `docker build`) no live env exists, and
// several client pages construct a Supabase client at module scope or during
// the prerender pass. Throwing there kills the image build. In the build
// phase only, hand back inert placeholders; at runtime the strict throws
// below still fire on real misconfiguration.
const isBuildPhase = (): boolean =>
  process.env.NEXT_PHASE === 'phase-production-build';

const ensureUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  if (!url) {
    if (isBuildPhase()) return 'http://supabase-placeholder.invalid';
    throw new Error(
      'SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) is not configured. Run `make supa-start` + `make supa-status` and sync the values into pmoves/.env.local.'
    );
  }
  return url;
};

const ensureAnonKey = (): string => {
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  if (!key) {
    if (isBuildPhase()) return 'build-phase-placeholder';
    throw new Error(
      'SUPABASE_ANON_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY) is missing. Export the publishable key from `make supa-status` and add it to pmoves/.env.local.'
    );
  }
  return key;
};

const resolveBootJwt = (): string | undefined =>
  process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT;

const ensureServiceRoleKey = (): string => {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY is missing. Copy the service role key from `make supa-status` into pmoves/.env.local before using server-side helpers.'
    );
  }
  return key;
};

let cachedBrowserClient: SupabaseClient<Database> | null = null;
let cachedRestUrl: string | null = null;

export type TypedSupabaseClient = SupabaseClient<Database>;

export function syncSessionToCookie(session: Session | null): void {
  if (typeof window === 'undefined') return;
  try {
    const cookieName = `sb-${new URL(ensureUrl()).hostname}-auth-token`;
    if (session) {
      const val = JSON.stringify({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
        expires_at: session.expires_at,
        token_type: session.token_type,
        user: session.user,
      });
      document.cookie = `${cookieName}=${encodeURIComponent(val)}; path=/; max-age=${session.expires_in ?? 3600}; SameSite=Lax`;
    } else {
      document.cookie = `${cookieName}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    }
  } catch { /* SSR guard */ }
}

export const createSupabaseBrowserClient = (): TypedSupabaseClient => {
  const bootJwt = resolveBootJwt();
  const validBoot = bootJwt && !isBootJwtExpired(5);
  const client = createClient<Database>(ensureUrl(), ensureAnonKey(), {
    auth: {
      autoRefreshToken: !validBoot,
      persistSession: !validBoot,
      detectSessionInUrl: !validBoot,
    },
    global: validBoot
      ? {
          headers: {
            Authorization: `Bearer ${bootJwt}`,
          },
        }
      : undefined,
  });
  if (typeof window !== 'undefined' && !validBoot) {
    client.auth.onAuthStateChange((_event, session) => {
      syncSessionToCookie(session);
    });
  }
  return client;
};

export const getSupabaseBrowserClient = (): TypedSupabaseClient => {
  if (!cachedBrowserClient) {
    cachedBrowserClient = createSupabaseBrowserClient();
  }
  return cachedBrowserClient;
};

export const getSupabaseRestUrl = (): string => {
  if (cachedRestUrl) {
    return cachedRestUrl;
  }
  const explicit = process.env.NEXT_PUBLIC_SUPABASE_REST_URL || process.env.SUPABASE_REST_URL;
  if (explicit) {
    cachedRestUrl = explicit.replace(/\/$/, '');
    return cachedRestUrl;
  }
  cachedRestUrl = `${ensureUrl().replace(/\/$/, '')}/rest/v1`;
  return cachedRestUrl;
};

export const createSupabaseServerClient = (
  options: SupabaseClientOptions = {}
): TypedSupabaseClient => {
  const { serviceRole = false } = options;
  const key = serviceRole ? ensureServiceRoleKey() : ensureAnonKey();
  const bootJwt = !serviceRole ? resolveBootJwt() : undefined;
  const validBoot = bootJwt && !isBootJwtExpired(5);
  return createClient<Database>(ensureUrl(), key, {
    auth: {
      autoRefreshToken: serviceRole ? false : !validBoot,
      persistSession: false,
    },
    global: validBoot
      ? {
          headers: {
            Authorization: `Bearer ${bootJwt}`,
          },
        }
      : undefined,
  });
};

export const createSupabaseServiceRoleClient = (): TypedSupabaseClient =>
  createSupabaseServerClient({ serviceRole: true });

export const getBootJwt = (): string | undefined => resolveBootJwt();

export const hasBootJwt = (): boolean => Boolean(resolveBootJwt());

function decodeJwtExp(token: string | undefined): number | null {
  try {
    if (!token) return null;
    const [, payload] = token.split('.') as [string, string, string];
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = JSON.parse(Buffer.from(base64, 'base64').toString('utf-8')) as { exp?: number };
    return typeof json.exp === 'number' ? json.exp : null;
  } catch {
    return null;
  }
}

export const isBootJwtExpired = (graceSeconds = 0): boolean => {
  const exp = decodeJwtExp(resolveBootJwt());
  // Security: treat missing exp claim as expired (fail-closed)
  if (!exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return now + graceSeconds >= exp;
};

export const getBootUser = async (client: TypedSupabaseClient) => {
  const bootJwt = resolveBootJwt();
  if (!bootJwt) {
    return null;
  }
  // Short-circuit if obviously expired to avoid noisy loops
  if (isBootJwtExpired(5)) {
    return null;
  }
  try {
    const { data, error } = await client.auth.getUser(bootJwt);
    if (error) {
      logError('Failed to fetch boot user via JWT', error, 'warning', { errorId: ErrorIds.SUPABASE_AUTH_FAILED, component: 'supabaseClient' });
      return null;
    }
    return data.user ?? null;
  } catch (err) {
    logError('Unexpected error when fetching boot user', err, 'warning', { errorId: ErrorIds.SUPABASE_AUTH_FAILED, component: 'supabaseClient' });
    return null;
  }
};
