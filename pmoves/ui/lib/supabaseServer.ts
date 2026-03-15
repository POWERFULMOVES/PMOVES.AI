import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { createServerClient } from '@supabase/ssr';
import type { NextRequest, NextResponse } from 'next/server';
import type { Database } from './database.types';

type ServiceClientOptions = {
  serviceKey?: string;
};

let serviceClient: SupabaseClient<Database> | null = null;

export function getServiceSupabaseClient(options: ServiceClientOptions = {}): SupabaseClient<Database> {
  if (serviceClient) {
    return serviceClient;
  }
  const url = process.env.SUPABASE_SERVICE_URL || process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = options.serviceKey || process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY;
  if (!url || !serviceKey) {
    throw new Error('Supabase service client requires SUPABASE_SERVICE_URL (or SUPABASE_URL) and SUPABASE_SERVICE_ROLE_KEY.');
  }
  serviceClient = createClient(url, serviceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
    global: {
      headers: {
        apikey: serviceKey,
        authorization: `Bearer ${serviceKey}`,
      },
    },
  });
  return serviceClient;
}

export const createSupabaseRouteHandlerClient = (
  cookieStore: { getAll(): { name: string; value: string }[]; set(...args: any[]): any }
) => {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error('Supabase URL and anon key required for route handler client');
  }
  return createServerClient<Database>(url, key, {
    cookies: {
      getAll() { return cookieStore.getAll(); },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          try { cookieStore.set(name, value, options); } catch { /* read-only in server components */ }
        });
      },
    },
  });
};

export const createSupabaseProxyClient = (args: {
  req: NextRequest;
  res: NextResponse;
}) => {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error('Supabase URL and anon key required for proxy client');
  }
  return createServerClient<Database>(url, key, {
    cookies: {
      getAll() { return args.req.cookies.getAll(); },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          args.req.cookies.set(name, value);
          args.res.cookies.set(name, value, options);
        });
      },
    },
  });
};
