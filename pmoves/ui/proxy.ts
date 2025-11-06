import { NextResponse, type NextRequest } from 'next/server';
import { createSupabaseProxyClient } from '@/lib/supabaseServer';

const PUBLIC_PATHS = new Set(['/', '/login', '/callback', '/icon.svg', '/favicon.ico']);

const isPublicPath = (pathname: string) => {
  if (PUBLIC_PATHS.has(pathname)) {
    return true;
  }
  if (pathname.startsWith('/dashboard/services')) {
    return true;
  }
  return pathname.startsWith('/_next') || pathname.startsWith('/api/auth');
};

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // If the app is configured with a boot JWT, treat the request as authenticated
  // (the server/client libraries already attach Authorization via env). This avoids
  // redirect loops when no Supabase cookie session exists.
  const bootJwt =
    process.env.NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT || process.env.SUPABASE_BOOT_USER_JWT;
  if (bootJwt) {
    return NextResponse.next();
  }

  const response = NextResponse.next();
  const supabase = createSupabaseProxyClient({ req: request, res: response });
  const {
    data: { session }
  } = await supabase.auth.getSession();

  if (!session) {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = '/login';
    const target = `${pathname}${request.nextUrl.search}`;
    redirectUrl.searchParams.set('next', target);
    return NextResponse.redirect(redirectUrl);
  }

  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)']
};
