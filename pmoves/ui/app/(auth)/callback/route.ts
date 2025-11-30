import { cookies } from 'next/headers';
import { NextResponse, type NextRequest } from 'next/server';
import { createSupabaseRouteHandlerClient } from '@/lib/supabaseServer';

const sanitizeRedirect = (value: string | null, origin: string): string => {
  if (!value) return origin;
  if (!value.startsWith('/')) {
    return origin;
  }
  return new URL(value, origin).toString();
};

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const next = requestUrl.searchParams.get('next');
  const code = requestUrl.searchParams.get('code');
  const error = requestUrl.searchParams.get('error');
  const origin = requestUrl.origin;

  if (error) {
    const redirectUrl = new URL('/login', origin);
    if (next && next.startsWith('/')) {
      redirectUrl.searchParams.set('next', next);
    }
    redirectUrl.searchParams.set('error', error);
    return NextResponse.redirect(redirectUrl);
  }

  if (code) {
    const cookieStore = await cookies();
    const supabase = createSupabaseRouteHandlerClient(() => cookieStore);
    try {
      await supabase.auth.exchangeCodeForSession(code);
    } catch (exchangeError) {
      console.error('Failed to exchange code for session', exchangeError);
      const redirectUrl = new URL('/login', origin);
      if (next && next.startsWith('/')) {
        redirectUrl.searchParams.set('next', next);
      }
      redirectUrl.searchParams.set('error', 'auth');
      return NextResponse.redirect(redirectUrl);
    }
  }

  const destination = sanitizeRedirect(next, origin);
  return NextResponse.redirect(destination);
}
