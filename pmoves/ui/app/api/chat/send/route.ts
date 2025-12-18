import { NextRequest, NextResponse } from 'next/server';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';
import { ownerFromJwt } from '@/lib/jwtUtils';
import { logError, logForDebugging } from '@/lib/errorUtils';

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

  const { content, role = 'user', agent, avatar_url } = body as {
    content?: string;
    role?: string;
    agent?: string;
    avatar_url?: string;
  };
  // Security: User identity must come from JWT only, never from request body
  const { ownerId: jwtOwner, error: jwtError } = ownerFromJwt('chat/send');
  const owner = jwtOwner;

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
