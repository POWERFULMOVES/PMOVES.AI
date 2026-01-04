'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  AuthResponse,
  Session,
  SignInWithOAuthCredentials,
  SignInWithPasswordCredentials
} from '@supabase/supabase-js';
import { createSupabaseBrowserClient, getBootJwt } from '@/lib/supabaseClient';

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

    const bootJwt = getBootJwt();

    const decodeJwt = (token: string): { exp?: number } => {
      try {
        const payload = token.split('.')[1];
        if (!payload) return {};
        const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
        const decoded = atob(normalized.padEnd(normalized.length + (4 - (normalized.length % 4)) % 4, '='));
        return JSON.parse(decoded);
      } catch (error) {
        console.warn('[useSupabaseAuth] Failed to decode boot JWT', error);
        return {};
      }
    };

    const bootstrap = async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (!active) return;
        let nextSession = data.session ?? null;

        if (!nextSession && bootJwt) {
          const { data: userData } = await supabase.auth.getUser(bootJwt);
          if (userData?.user) {
            const claims = decodeJwt(bootJwt);
            const now = Math.floor(Date.now() / 1000);
            const exp = typeof claims.exp === 'number' ? claims.exp : now + 3600;
            nextSession = {
              access_token: bootJwt,
              token_type: 'bearer',
              expires_at: exp,
              expires_in: Math.max(0, exp - now),
              refresh_token: bootJwt,
              provider_refresh_token: null,
              provider_token: null,
              user: userData.user,
            } as Session;
          }
        }

        setSession(nextSession);
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
