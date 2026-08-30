import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createSupabaseRouteHandlerClient } from '@/lib/supabaseServer';
import { loadRoom, loadRooms } from '@/lib/rooms';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createSupabaseRouteHandlerClient(cookieStore);
  const { data: { session } } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const roomId = request.nextUrl.searchParams.get('room_id');
  const headers = {
    'Cache-Control': 'private, max-age=30, stale-while-revalidate=60',
    'Content-Type': 'application/json',
  };

  try {
    if (roomId) {
      const room = await loadRoom(roomId);
      if (!room) {
        return NextResponse.json({ error: 'Room not found' }, { status: 404, headers });
      }

      return NextResponse.json(
        {
          room,
          generatedAt: new Date().toISOString(),
        },
        { headers }
      );
    }

    const rooms = await loadRooms();
    return NextResponse.json(
      {
        rooms,
        total: rooms.length,
        generatedAt: new Date().toISOString(),
      },
      { headers }
    );
  } catch (error) {
    console.error('Failed to load rooms:', error);
    return NextResponse.json(
      { error: 'Failed to load rooms' },
      { status: 500, headers }
    );
  }
}
