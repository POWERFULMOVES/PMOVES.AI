'use client';

import { createClient, SupabaseClient } from '@supabase/supabase-js';

let browserClient: SupabaseClient | null = null;

export function getBrowserSupabaseClient(): SupabaseClient {
  if (browserClient) {
    return browserClient;
  }
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error('Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY environment variables.');
  }
  browserClient = createClient(url, anonKey, {
    auth: {
      persistSession: false,
    },
  });
  return browserClient;
}
