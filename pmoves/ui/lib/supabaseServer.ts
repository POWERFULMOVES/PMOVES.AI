import { createMiddlewareClient, createRouteHandlerClient } from '@supabase/auth-helpers-nextjs';
import type { Cookies } from 'next/headers';
import type { NextRequest, NextResponse } from 'next/server';

export type Database = Record<string, never>;

export const createSupabaseRouteHandlerClient = (cookies: () => Cookies) =>
  createRouteHandlerClient<Database>({ cookies });

export const createSupabaseMiddlewareClient = (args: {
  req: NextRequest;
  res: NextResponse;
}) => createMiddlewareClient<Database>(args);
