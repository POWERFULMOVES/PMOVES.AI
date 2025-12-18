import { NextRequest, NextResponse } from 'next/server';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';
import { getBootJwt } from '@/lib/supabaseClient';
import { logError, logForDebugging } from '@/lib/errorUtils';

function ownerFromJwt(): { ownerId: string | null; error?: string } {
  try {
    const token = getBootJwt();
    if (!token) {
      return { ownerId: null, error: 'No JWT token available' };
    }
    const parts = token.split('.');
    if (parts.length !== 3) {
      logError('Invalid JWT format', new Error('JWT must have 3 parts'), 'warning', { component: 'chat/send' });
      return { ownerId: null, error: 'Invalid JWT format' };
    }
    const payload = parts[1];
    const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
    return { ownerId: typeof json.sub === 'string' ? json.sub : null };
  } catch (e) {
    logError('JWT parsing failed', e, 'error', { component: 'chat/send' });
    return { ownerId: null, error: 'Failed to parse JWT' };
  }
}

export async function POST(req: NextRequest) {
  const supabase = getServiceSupabaseClient();

  // Parse JSON body with explicit error logging
  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch (e) {
    logForDebugging('Failed to parse request JSON', e, { component: 'chat/send' });
    return NextResponse.json(
      { ok: false, error: 'Invalid request body (malformed JSON)' },
      { status: 400 }
    );
  }

  const { content, role = 'user', agent, avatar_url, ownerId: bodyOwnerId } = body as {
    content?: string;
    role?: string;
    agent?: string;
    avatar_url?: string;
    ownerId?: string;
  };
  const { ownerId: jwtOwner, error: jwtError } = ownerFromJwt();
  const owner = bodyOwnerId ?? jwtOwner;

  if (!owner) {
    return NextResponse.json(
      { ok: false, error: jwtError || 'Authentication required' },
      { status: 401 }
    );
  }
  if (!content || typeof content !== 'string') {
    return NextResponse.json({ ok: false, error: 'content required' }, { status: 400 });
  }

  const { data, error } = await supabase
    .from('chat_messages')
    .insert([{ owner_id: owner, content, role, agent, avatar_url }])
    .select('id,role,agent,avatar_url,content,created_at')
    .single();
  if (error) {
    logError('Failed to send chat message', error, 'error', {
      component: 'chat/send',
      owner,
    });
    return NextResponse.json(
      { ok: false, error: 'Failed to send message. Please try again.' },
      { status: 500 }
    );
  }
  return NextResponse.json({ ok: true, message: data });
}

