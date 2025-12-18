import { NextRequest, NextResponse } from 'next/server';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';
import { getBootJwt } from '@/lib/supabaseClient';
import { logError } from '@/lib/errorUtils';

function ownerFromJwt(): { ownerId: string | null; error?: string } {
  try {
    const token = getBootJwt();
    if (!token) {
      return { ownerId: null, error: 'No JWT token available' };
    }
    const parts = token.split('.');
    if (parts.length !== 3) {
      logError('Invalid JWT format', new Error('JWT must have 3 parts'), 'warning', { component: 'chat/messages' });
      return { ownerId: null, error: 'Invalid JWT format' };
    }
    const payload = parts[1];
    const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
    return { ownerId: typeof json.sub === 'string' ? json.sub : null };
  } catch (e) {
    logError('JWT parsing failed', e, 'error', { component: 'chat/messages' });
    return { ownerId: null, error: 'Failed to parse JWT' };
  }
}

export async function GET(req: NextRequest) {
  const supabase = getServiceSupabaseClient();
  // Security: User identity must come from JWT only, never from query params
  const { ownerId: jwtOwner, error: jwtError } = ownerFromJwt();
  const ownerId = jwtOwner;

  if (!ownerId) {
    // Return 401 when no owner ID is available - don't silently return empty array
    return NextResponse.json(
      { error: jwtError || 'Authentication required', items: [] },
      { status: 401 }
    );
  }

  const { data, error } = await supabase
    .from('chat_messages')
    .select('id,role,agent,avatar_url,content,created_at')
    .eq('owner_id', ownerId)
    .order('created_at', { ascending: false })
    .limit(50);
  if (error) {
    logError('Failed to fetch chat messages', error, 'error', {
      component: 'chat/messages',
      ownerId,
    });
    return NextResponse.json(
      { error: 'Failed to load messages. Please try again.' },
      { status: 500 }
    );
  }
  return NextResponse.json({ items: data ?? [] });
}

