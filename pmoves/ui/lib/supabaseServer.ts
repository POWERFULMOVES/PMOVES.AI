import { createClient, SupabaseClient } from '@supabase/supabase-js';

type ServiceClientOptions = {
  serviceKey?: string;
};

let serviceClient: SupabaseClient | null = null;

export function getServiceSupabaseClient(options: ServiceClientOptions = {}): SupabaseClient {
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
import { createMiddlewareClient, createRouteHandlerClient } from '@supabase/auth-helpers-nextjs';
import type { Cookies } from 'next/headers';
import type { NextRequest, NextResponse } from 'next/server';

export type Database = Record<string, never>;

export const createSupabaseRouteHandlerClient = (cookies: () => Cookies) =>
  createRouteHandlerClient<Database>({ cookies });

export const createSupabaseMiddlewareClient = (args: {
  req: NextRequest;
  res: NextResponse;
}) => createMiddlewareClient<Database>(args);
