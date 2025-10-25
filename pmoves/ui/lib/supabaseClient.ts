import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null = null;

interface ClientOptions {
  url?: string;
  anonKey?: string;
}

const defaultOptions: ClientOptions = {
  url:
    process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ||
    process.env.SUPABASE_URL?.trim(),
  anonKey:
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ||
    process.env.SUPABASE_ANON_KEY?.trim(),
};

export function getSupabaseBrowserClient(
  opts: ClientOptions = {}
): SupabaseClient {
  if (browserClient) {
    return browserClient;
  }

  const url = (opts.url ?? defaultOptions.url) || "";
  const anonKey = (opts.anonKey ?? defaultOptions.anonKey) || "";

  if (!url || !anonKey) {
    throw new Error(
      "Supabase client requires NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY (or server-side equivalents)."
    );
  }

  browserClient = createClient(url, anonKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });

  return browserClient;
}

export function getSupabaseRestUrl(): string | null {
  const explicit =
    process.env.NEXT_PUBLIC_SUPABASE_REST_URL?.trim() ||
    process.env.SUPABASE_REST_URL?.trim();
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }

  const url = defaultOptions.url;
  if (!url) {
    return null;
  }

  return `${url.replace(/\/$/, "")}/rest/v1`;
}
import { createBrowserClient } from '@supabase/auth-helpers-nextjs';
import type { SupabaseClient } from '@supabase/supabase-js';

type Database = Record<string, never>;

const requiredEnv = (key: string): string => {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
};

export const createSupabaseBrowserClient = (): SupabaseClient<Database> => {
  const url = requiredEnv('NEXT_PUBLIC_SUPABASE_URL');
  const anonKey = requiredEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY');
  return createBrowserClient<Database>(url, anonKey);
};
import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { uiConfig } from "@/config";
import type { Database } from "./database.types";

type SupabaseClientOptions = {
  serviceRole?: boolean;
};

const { supabaseUrl, supabaseAnonKey, supabaseServiceRoleKey } = uiConfig;

const ensureAnonKey = () => {
  if (!supabaseAnonKey) {
    throw new Error(
      "SUPABASE_ANON_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY) is not configured. Run `make supa-status` after `make supa-start` and copy the publishable key into pmoves/.env.local."
    );
  }
  return supabaseAnonKey;
};

const ensureServiceRoleKey = () => {
  if (!supabaseServiceRoleKey) {
    throw new Error(
      "SUPABASE_SERVICE_ROLE_KEY is missing. Export the service role key from `make supa-status` and add it to pmoves/.env.local before using server-side helpers."
    );
  }
  return supabaseServiceRoleKey;
};

const ensureUrl = () => {
  if (!supabaseUrl) {
    throw new Error(
      "SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) is not configured. Populate pmoves/.env.local via the Supabase CLI bring-up documented in pmoves/docs/LOCAL_DEV.md."
    );
  }
  return supabaseUrl;
};

export type TypedSupabaseClient = SupabaseClient<Database>;

export const createSupabaseBrowserClient = (): TypedSupabaseClient => {
  return createClient<Database>(ensureUrl(), ensureAnonKey(), {
    auth: {
      autoRefreshToken: true,
      persistSession: true,
    },
  });
};

export const createSupabaseServerClient = (
  options: SupabaseClientOptions = {}
): TypedSupabaseClient => {
  const { serviceRole = false } = options;
  const key = serviceRole ? ensureServiceRoleKey() : ensureAnonKey();
  return createClient<Database>(ensureUrl(), key, {
    auth: {
      autoRefreshToken: !serviceRole,
      persistSession: false,
    },
  });
};

export const createSupabaseServiceRoleClient = (): TypedSupabaseClient =>
  createSupabaseServerClient({ serviceRole: true });
