'use client';

import type { ChangeEvent, FormEvent } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSupabaseAuth } from '@/hooks/useSupabaseAuth';
import type { SupabaseOAuthProvider } from '@/config/supabaseProviders';

type LoginFormProps = {
  providers: SupabaseOAuthProvider[];
  passwordEnabled: boolean;
  callbackUrl: string;
  nextPath?: string;
  initialError?: string | null;
};

type FormState = {
  email: string;
  password: string;
};

const initialFormState: FormState = {
  email: '',
  password: ''
};

const sanitizeRedirect = (input?: string): string => {
  if (!input) return '/';
  if (!input.startsWith('/')) {
    return '/';
  }
  return input;
};

export const LoginForm = ({ providers, passwordEnabled, callbackUrl, nextPath, initialError }: LoginFormProps) => {
  const router = useRouter();
  const { signInWithPassword, signInWithOAuth, loading, error } = useSupabaseAuth();
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [formError, setFormError] = useState<string | null>(initialError ?? null);
  const [status, setStatus] = useState<string | null>(null);

  const targetPath = useMemo(() => sanitizeRedirect(nextPath), [nextPath]);

  const handleChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormState((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handlePasswordLogin = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setFormError(null);
      setStatus(null);

      const { email, password } = formState;
      if (!email || !password) {
        setFormError('Email and password are required.');
        return;
      }

      const response = await signInWithPassword({ email, password });
      if (response.error) {
        setFormError(response.error.message);
        return;
      }

      setStatus('Signed in! Redirecting…');
      router.replace(targetPath);
    },
    [formState, router, signInWithPassword, targetPath]
  );

  const handleOAuthLogin = useCallback(
    async (provider: SupabaseOAuthProvider['key']) => {
      setFormError(null);
      setStatus(null);

      const redirectUrl = callbackUrl.startsWith('http')
        ? new URL(callbackUrl)
        : new URL(callbackUrl, window.location.origin);
      if (nextPath) {
        redirectUrl.searchParams.set('next', sanitizeRedirect(nextPath));
      }

      const response = await signInWithOAuth({
        provider,
        options: {
          redirectTo: redirectUrl.toString()
        }
      });

      if (response.error) {
        setFormError(response.error.message);
      } else if (response.data?.url) {
        window.location.href = response.data.url;
      }
    },
    [callbackUrl, nextPath, signInWithOAuth]
  );

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '2rem',
        width: '100%',
        maxWidth: '420px'
      }}
    >
      {passwordEnabled && (
        <form
          onSubmit={handlePasswordLogin}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
            padding: '1.5rem',
            borderRadius: '1rem',
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(148, 163, 184, 0.3)'
          }}
        >
          <div>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={formState.email}
              onChange={handleChange}
              required
              style={{
                marginTop: '0.5rem',
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '0.75rem',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                background: 'rgba(15, 23, 42, 0.6)',
                color: 'inherit'
              }}
            />
          </div>
          <div>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={formState.password}
              onChange={handleChange}
              required
              style={{
                marginTop: '0.5rem',
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '0.75rem',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                background: 'rgba(15, 23, 42, 0.6)',
                color: 'inherit'
              }}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '9999px',
              border: 'none',
              background: 'linear-gradient(135deg, #38bdf8, #6366f1)',
              color: '#0f172a',
              fontWeight: 600,
              cursor: 'pointer',
              opacity: loading ? 0.7 : 1
            }}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      )}

      {providers.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem'
          }}
        >
          <span style={{ opacity: 0.7 }}>Or sign in with</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {providers.map((provider) => (
              <button
                key={provider.key}
                onClick={() => handleOAuthLogin(provider.key)}
                type="button"
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '0.75rem',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  background: 'rgba(15, 23, 42, 0.6)',
                  color: 'inherit',
                  cursor: 'pointer'
                }}
              >
                Continue with {provider.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {(formError || error) && (
        <div style={{
          borderRadius: '0.75rem',
          padding: '1rem',
          border: '1px solid rgba(248, 113, 113, 0.4)',
          background: 'rgba(248, 113, 113, 0.1)',
          color: '#fecaca'
        }}>
          {formError || error}
        </div>
      )}

      {status && (
        <div
          style={{
            borderRadius: '0.75rem',
            padding: '1rem',
            border: '1px solid rgba(74, 222, 128, 0.4)',
            background: 'rgba(74, 222, 128, 0.1)',
            color: '#bbf7d0'
          }}
        >
          {status}
        </div>
      )}
    </div>
  );
};
