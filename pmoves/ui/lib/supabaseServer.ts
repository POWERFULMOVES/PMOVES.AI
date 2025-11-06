import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { createMiddlewareClient, createRouteHandlerClient } from '@supabase/auth-helpers-nextjs';
import type { ReadonlyRequestCookies } from 'next/dist/server/web/spec-extension/adapters/request-cookies';
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

type CookieSource = () => ReadonlyRequestCookies | Promise<ReadonlyRequestCookies> | unknown;

export const createSupabaseRouteHandlerClient = (cookies: CookieSource) =>
  createRouteHandlerClient<Database>({ cookies: cookies as any });

export const createSupabaseProxyClient = (args: {
  req: NextRequest;
  res: NextResponse;
}) => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
  // Pass explicit config so middleware works in edge runtime even if env scoping differs
  return createMiddlewareClient<Database>(args as any, (supabaseUrl && supabaseKey) ? { supabaseUrl, supabaseKey } : undefined);
};
