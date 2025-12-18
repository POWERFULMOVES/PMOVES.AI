import { NextRequest, NextResponse } from 'next/server';
import { getServiceSupabaseClient } from '@/lib/supabaseServer';
import { ownerFromJwt } from '@/lib/jwtUtils';
import { logError } from '@/lib/errorUtils';

export async function GET(req: NextRequest) {
  const supabase = getServiceSupabaseClient();
  // Security: User identity must come from JWT only, never from query params
  const { ownerId: jwtOwner, error: jwtError } = ownerFromJwt('chat/messages');
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
