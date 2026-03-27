import { NextRequest, NextResponse } from 'next/server';
import { ownerFromJwt } from '@/lib/jwtUtils';
import { loadRoom, loadRooms } from '@/lib/rooms';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const { ownerId, error: authError } = ownerFromJwt('rooms');
  if (authError || !ownerId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const roomId = request.nextUrl.searchParams.get('room_id');
  const headers = {
    'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
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
    return NextResponse.json(
      {
        error: 'Failed to load rooms',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500, headers }
    );
  }
}
