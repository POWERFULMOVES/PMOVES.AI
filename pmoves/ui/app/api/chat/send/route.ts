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

export async function POST(req: NextRequest) {
  const supabase = getServiceSupabaseClient();
  const body = await req.json().catch(() => ({}));
  let { content, role, agent, avatar_url, ownerId } = body as any;
  if (!ownerId) ownerId = ownerFromJwt();
  if (!ownerId) return NextResponse.json({ error: 'ownerId missing' }, { status: 400 });
  if (!content || typeof content !== 'string') return NextResponse.json({ error: 'content required' }, { status: 400 });
  role = role || 'user';
  const { data, error } = await supabase
    .from('chat_messages')
    .insert([{ owner_id: ownerId, content, role, agent, avatar_url }])
    .select('id,role,agent,avatar_url,content,created_at')
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, message: data });
}

