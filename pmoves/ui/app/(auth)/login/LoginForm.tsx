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
  if (!input.startsWith('/')) return '/';
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

      setStatus('Signed in! Redirecting...');
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
        options: { redirectTo: redirectUrl.toString() }
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
    <div className="w-full max-w-md space-y-6">
      {passwordEnabled && (
        <form onSubmit={handlePasswordLogin} className="card-brutal p-6 space-y-5">
          <div className="space-y-2">
            <label className="block text-sm font-mono uppercase tracking-wider text-ink-muted" htmlFor="email">
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
              className="w-full px-4 py-3 bg-void border border-border-subtle text-ink-primary font-mono text-sm placeholder:text-ink-muted focus:outline-none focus:border-cata-cyan focus:ring-2 focus:ring-cata-cyan/30 transition-colors"
              placeholder="you@example.com"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-mono uppercase tracking-wider text-ink-muted" htmlFor="password">
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
              className="w-full px-4 py-3 bg-void border border-border-subtle text-ink-primary font-mono text-sm placeholder:text-ink-muted focus:outline-none focus:border-cata-cyan focus:ring-2 focus:ring-cata-cyan/30 transition-colors"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      )}

      {providers.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex-1 h-px bg-border-subtle" />
            <span className="text-xs text-ink-muted uppercase tracking-wider">Or continue with</span>
            <div className="flex-1 h-px bg-border-subtle" />
          </div>

          <div className="space-y-3">
            {providers.map((provider) => (
              <button
                key={provider.key}
                onClick={() => handleOAuthLogin(provider.key)}
                type="button"
                className="w-full px-4 py-3 border border-border-subtle bg-void-elevated text-ink-primary font-display font-semibold text-sm uppercase tracking-wider hover:border-cata-cyan hover:text-cata-cyan transition-colors focus:outline-none focus:border-cata-cyan focus:ring-2 focus:ring-cata-cyan/30"
              >
                {provider.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error state */}
      {(formError || error) && (
        <div className="p-4 border border-cata-ember bg-cata-ember/10 flex items-start gap-3">
          <div className="w-6 h-6 flex items-center justify-center bg-cata-ember/20 text-cata-ember font-bold flex-shrink-0">
            !
          </div>
          <p className="text-sm text-cata-ember">{formError || error}</p>
        </div>
      )}

      {/* Success state */}
      {status && (
        <div className="p-4 border border-cata-forest bg-cata-forest/10 flex items-start gap-3">
          <div className="w-6 h-6 flex items-center justify-center bg-cata-forest/20 text-cata-forest font-bold flex-shrink-0">
            ✓
          </div>
          <p className="text-sm text-cata-forest">{status}</p>
        </div>
      )}
    </div>
  );
};
