'use client';

import { useEffect } from 'react';
import { createSupabaseBrowserClient } from '@/lib/supabaseClient';

const SupabaseDiagnostics = () => {
  useEffect(() => {
    createSupabaseBrowserClient();
  }, []);

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">Supabase diagnostics</h1>
      <p className="mt-4 text-muted-foreground">
        This route surfaces during Playwright tests to ensure boot JWTs are wired into the
        browser client. It is not linked from the operator console.
      </p>
    </main>
  );
};

export default SupabaseDiagnostics;
