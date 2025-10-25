'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  AuthResponse,
  Session,
  SignInWithOAuthCredentials,
  SignInWithPasswordCredentials
} from '@supabase/supabase-js';
import { createSupabaseBrowserClient } from '@/lib/supabaseClient';

type SupabaseBrowserClient = ReturnType<typeof createSupabaseBrowserClient>;
type OAuthSignInResponse = Awaited<ReturnType<SupabaseBrowserClient['auth']['signInWithOAuth']>>;

export type UseSupabaseAuthReturn = {
  session: Session | null;
  user: Session['user'] | null;
  loading: boolean;
  error: string | null;
  signInWithPassword: (credentials: SignInWithPasswordCredentials) => Promise<AuthResponse>;
  signInWithOAuth: (credentials: SignInWithOAuthCredentials) => Promise<OAuthSignInResponse>;
  signOut: () => Promise<void>;
};

export const useSupabaseAuth = (): UseSupabaseAuthReturn => {
  const [supabase] = useState(createSupabaseBrowserClient);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (!active) return;
        setSession(data.session ?? null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    bootstrap();

    const { data: listener } = supabase.auth.onAuthStateChange((_, nextSession) => {
      setSession(nextSession);
      setError(null);
    });

    supabase.auth.startAutoRefresh();

    return () => {
      active = false;
      listener?.subscription.unsubscribe();
      supabase.auth.stopAutoRefresh();
    };
  }, [supabase]);

  const signInWithPassword = useCallback(
    async (credentials: SignInWithPasswordCredentials) => {
      setLoading(true);
      setError(null);
      const response = await supabase.auth.signInWithPassword(credentials);
      if (response.error) {
        setError(response.error.message);
      }
      setLoading(false);
      return response;
    },
    [supabase]
  );

  const signInWithOAuth = useCallback(
    async (credentials: SignInWithOAuthCredentials) => {
      setError(null);
      const response = await supabase.auth.signInWithOAuth(credentials);
      if (response.error) {
        setError(response.error.message);
      }
      return response;
    },
    [supabase]
  );

  const signOut = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { error: signOutError } = await supabase.auth.signOut();
    if (signOutError) {
      setError(signOutError.message);
    }
    setLoading(false);
  }, [supabase]);

  const user = useMemo(() => session?.user ?? null, [session]);

  return {
    session,
    user,
    loading,
    error,
    signInWithPassword,
    signInWithOAuth,
    signOut
  };
};
