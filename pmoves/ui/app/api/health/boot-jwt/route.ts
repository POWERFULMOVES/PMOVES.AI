import { NextRequest, NextResponse } from 'next/server';
import { authenticateRequest } from '@/lib/jwtUtils';
import { getBootJwt } from '@/lib/supabaseClient';

interface JwtPayload {
  exp?: number;
  iss?: string;
  sub?: string;
}

function decode(token?: string): JwtPayload | null {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    let base64 = parts[1];
    base64 = base64.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) base64 += '=';
    return JSON.parse(Buffer.from(base64, 'base64').toString('utf-8')) as JwtPayload;
  } catch {
    return null;
  }
}

export async function GET(req: NextRequest) {
  const { ownerId, error: authError } = authenticateRequest(req, 'health/boot-jwt');
  if (!ownerId) {
    return NextResponse.json({ error: authError || 'Authentication required' }, { status: 401 });
  }

  const token = getBootJwt();
  const payload = decode(token || undefined);
  const now = Math.floor(Date.now() / 1000);
  const exp = payload?.exp;
  const expired = !!(exp && now >= exp);
  return NextResponse.json({
    hasToken: Boolean(token),
    exp,
    now,
    expired,
    iss: payload?.iss,
    // Security: sub (user UUID) redacted from response
  });
}
