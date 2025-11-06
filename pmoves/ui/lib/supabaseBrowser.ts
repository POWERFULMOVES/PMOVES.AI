'use client';

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './database.types';
import { createSupabaseBrowserClient } from './supabaseClient';

let browserClient: SupabaseClient<Database> | null = null;

export function getBrowserSupabaseClient(): SupabaseClient<Database> {
  if (!browserClient) {
    // Single browser client that respects boot-JWT (no cookie session)
    browserClient = createSupabaseBrowserClient();
  }
  return browserClient as SupabaseClient<Database>;
}
