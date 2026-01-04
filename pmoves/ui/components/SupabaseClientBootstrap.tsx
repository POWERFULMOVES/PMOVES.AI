'use client';

import { useEffect } from 'react';
import { getBrowserSupabaseClient } from '@/lib/supabaseBrowser';

export function SupabaseClientBootstrap() {
  useEffect(() => {
    try {
      getBrowserSupabaseClient();
    } catch (error) {
      console.warn('Failed to initialize Supabase client helpers', error);
    }
  }, []);

  return null;
}
