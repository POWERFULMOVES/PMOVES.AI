import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './database.types';

type SupabaseClientOptions = {
  serviceRole?: boolean;
};

const ensureUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  if (!url) {
    throw new Error(
      'SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) is not configured. Run `make supa-start` + `make supa-status` and sync the values into pmoves/.env.local.'
    );
  }
  return url;
};

const ensureAnonKey = (): string => {
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  if (!key) {
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

export const createSupabaseBrowserClient = (): TypedSupabaseClient => {
  const bootJwt = resolveBootJwt();
  const client = createClient<Database>(ensureUrl(), ensureAnonKey(), {
    auth: {
      autoRefreshToken: !bootJwt,
      persistSession: !bootJwt,
    },
    global: bootJwt
      ? {
          headers: {
            Authorization: `Bearer ${bootJwt}`,
          },
        }
      : undefined,
  });
  if (typeof window !== 'undefined') {
    (window as any).__PMOVES_SUPABASE_BOOT = {
      hasBootJwt: Boolean(bootJwt),
      authorization: bootJwt ? `Bearer ${bootJwt}` : undefined,
    };
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
  return createClient<Database>(ensureUrl(), key, {
    auth: {
      autoRefreshToken: serviceRole ? false : !bootJwt,
      persistSession: false,
    },
    global: bootJwt
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

export const getBootUser = async (client: TypedSupabaseClient) => {
  const bootJwt = resolveBootJwt();
  if (!bootJwt) {
    return null;
  }
  try {
    const { data, error } = await client.auth.getUser(bootJwt);
    if (error) {
      console.warn('[supabaseClient] Failed to fetch boot user via JWT', error);
      return null;
    }
    return data.user ?? null;
  } catch (err) {
    console.warn('[supabaseClient] Unexpected error when fetching boot user', err);
    return null;
  }
};
