'use client';

import type { ChangeEvent, FormEvent } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSupabaseAuth } from '@/hooks/useSupabaseAuth';
import type { Provider } from '@supabase/supabase-js';
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
    async (providerKey: SupabaseOAuthProvider['key']) => {
      setFormError(null);
      setStatus(null);

      const redirectUrl = callbackUrl.startsWith('http')
        ? new URL(callbackUrl)
        : new URL(callbackUrl, window.location.origin);
      if (nextPath) {
        redirectUrl.searchParams.set('next', sanitizeRedirect(nextPath));
      }

      const response = await signInWithOAuth({
        provider: providerKey as Provider,
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
    <div className="flex w-full max-w-md flex-col gap-8">
      {passwordEnabled && (
        <form
          onSubmit={handlePasswordLogin}
          className="flex flex-col gap-4 rounded-2xl border border-brand-border bg-[rgba(16,43,47,0.85)] p-6 text-brand-inverse shadow-lg shadow-[rgba(16,43,47,0.25)]"
        >
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={formState.email}
              onChange={handleChange}
              required
              className="w-full rounded-lg border border-brand-border bg-[rgba(16,43,47,0.6)] px-4 py-3 text-sm text-brand-inverse placeholder:text-brand-subtle focus:outline-none focus:ring-2 focus:ring-brand-sky"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={formState.password}
              onChange={handleChange}
              required
              className="w-full rounded-lg border border-brand-border bg-[rgba(16,43,47,0.6)] px-4 py-3 text-sm text-brand-inverse placeholder:text-brand-subtle focus:outline-none focus:ring-2 focus:ring-brand-sky"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="rounded-full bg-brand-sky px-4 py-3 text-sm font-semibold text-brand-ink-strong transition hover:bg-brand-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 focus-visible:ring-offset-brand-inverse disabled:opacity-70"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      )}

      {providers.length > 0 && (
        <div className="flex flex-col gap-3 text-brand-inverse">
          <span className="text-sm text-brand-subtle">Or sign in with</span>
          <div className="flex flex-col gap-2">
            {providers.map((provider) => (
              <button
                key={provider.key}
                onClick={() => handleOAuthLogin(provider.key)}
                type="button"
                className="rounded-xl border border-brand-border bg-[rgba(16,43,47,0.6)] px-4 py-3 text-sm font-medium text-brand-inverse transition hover:border-brand-sky hover:text-brand-inverse focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-sky"
              >
                Continue with {provider.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {(formError || error) && (
        <div className="rounded-xl border border-brand-crimson bg-[rgba(219,69,69,0.15)] p-4 text-sm text-brand-crimson">
          {formError || error}
        </div>
      )}

      {status && (
        <div className="rounded-xl border border-brand-forest bg-[rgba(46,139,87,0.18)] p-4 text-sm text-brand-forest">
          {status}
        </div>
      )}
    </div>
  );
};
