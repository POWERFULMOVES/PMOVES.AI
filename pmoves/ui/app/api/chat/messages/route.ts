import { NextRequest, NextResponse } from 'next/server';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';
import { getBootJwt } from '@/lib/supabaseClient';

function ownerFromJwt(): string | null {
  try {
    const token = getBootJwt();
    if (!token) return null;
    const [, payload] = token.split('.') as [string, string, string];
    const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
    return typeof json.sub === 'string' ? json.sub : null;
  } catch {
    return null;
  }
}

export async function GET(req: NextRequest) {
  const supabase = getServiceSupabaseClient();
  const owner = ownerFromJwt();
  const ownerId = owner || req.nextUrl.searchParams.get('ownerId');
  if (!ownerId) return NextResponse.json({ items: [] });
  const { data, error } = await supabase
    .from('chat_messages')
    .select('id,role,agent,avatar_url,content,created_at')
    .eq('owner_id', ownerId)
    .order('created_at', { ascending: false })
    .limit(50);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ items: data ?? [] });
}

