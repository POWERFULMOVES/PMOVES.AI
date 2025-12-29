/* ═══════════════════════════════════════════════════════════════════════════
   Jellyfin API Client Tests
   Tests Jellyfin Bridge integration for media linking
   ═══════════════════════════════════════════════════════════════════════════ */

import {
  jellyfinSearch,
  jellyfinSyncStatus,
  linkJellyfinItem,
  getJellyfinPlaybackUrl,
  triggerJellyfinSync,
  triggerBackfill,
} from './jellyfin';

// Mock fetch
global.fetch = jest.fn();

// Mock errorUtils
jest.mock('../errorUtils', () => ({
  logError: jest.fn(),
  ok: (value: unknown) => ({ ok: true, data: value }),
  err: (error: string) => ({ ok: false, error }),
  getErrorMessage: (status: number) => `HTTP Error ${status}`,
}));

describe('Jellyfin API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NEXT_PUBLIC_JELLYFIN_BRIDGE_URL = undefined;
  });

  describe('jellyfinSearch', () => {
    it('should fetch sync status', async () => {
      const mockSyncStatus = {
        status: 'idle' as const,
        lastSync: '2025-01-15T10:00:00Z',
        videosLinked: 42,
        pendingBackfill: 15,
        errors: 0,
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSyncStatus,
      } as Response);

      const result = await jellyfinSyncStatus();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.videosLinked).toBe(42);
      }
    });

    it('should search library with term', async () => {
      const mockItems = [
        {
          id: '1',
          name: 'Test Movie',
          type: 'Movie' as const,
          productionYear: 2024,
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: mockItems }),
      } as Response);

      const result = await jellyfinSearch('test query');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toHaveLength(1);
        expect(result.data[0].name).toBe('Test Movie');
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/jellyfin/search?');
    });

    it('should filter by media type', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);

      await jellyfinSearch('test', { mediaType: 'Episode', limit: 20 });

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('media_type=Episode');
    });

    it('should handle service unavailable', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 503,
      } as Response);

      const result = await jellyfinSearch('test');

      expect(result.ok).toBe(false);
    });

    it('should return empty array when items field missing', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await jellyfinSearch('test');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toEqual([]);
      }
    });
  });

  describe('linkJellyfinItem', () => {
    it('should link video to Jellyfin item', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await linkJellyfinItem('abc123', 'jellyfin-item-1');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.linked).toBe(true);
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/jellyfin/link');

      const body = JSON.parse(fetchCalls[0][1]?.body as string);
      expect(body.video_id).toBe('abc123');
    });

    it('should handle linking failure', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      const result = await linkJellyfinItem('abc123', 'unknown-item');

      expect(result.ok).toBe(false);
    });
  });

  describe('getJellyfinPlaybackUrl', () => {
    it('should generate playback URL with timestamp', async () => {
      const mockPlaybackUrl = {
        url: 'https://jellyfin.example.com/videos/123.mp4',
        startPosition: 60,
        expiresAt: '2025-01-15T12:00:00Z',
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPlaybackUrl,
      } as Response);

      const result = await getJellyfinPlaybackUrl('item-123', 60);

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.url).toContain('jellyfin.example.com');
        expect(result.data.startPosition).toBe(60);
      }
    });

    it('should generate playback URL without timestamp', async () => {
      const mockPlaybackUrl = {
        url: 'https://jellyfin.example.com/videos/123.mp4',
        expiresAt: '2025-01-15T12:00:00Z',
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPlaybackUrl,
      } as Response);

      const result = await getJellyfinPlaybackUrl('item-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.startPosition).toBeUndefined();
      }
    });
  });

  describe('triggerJellyfinSync', () => {
    it('should trigger sync operation', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await triggerJellyfinSync();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.started).toBe(true);
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/jellyfin/sync');
    });

    it('should handle sync already in progress', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 409,
      } as Response);

      const result = await triggerJellyfinSync();

      expect(result.ok).toBe(false);
    });
  });

  describe('triggerBackfill', () => {
    it('should trigger backfill with default limit', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await triggerBackfill({});

      expect(result.ok).toBe(true);

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/jellyfin/backfill');

      const body = JSON.parse(fetchCalls[0][1]?.body as string);
      expect(body).toEqual({});
    });

    it('should trigger backfill with options', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await triggerBackfill({
        channelId: 'UCxxx',
        limit: 100,
      });

      expect(result.ok).toBe(true);

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/jellyfin/backfill');

      const body = JSON.parse(fetchCalls[0][1]?.body as string);
      expect(body.channelId).toBe('UCxxx');
      expect(body.limit).toBe(100);
    });
  });

  describe('validate backfill options', () => {
    it('should handle large limit values', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await triggerBackfill({ limit: 1000 });

      expect(result.ok).toBe(true);

      const body = JSON.parse((global.fetch as jest.MockedFunction<typeof fetch>).mock.calls[0][1]?.body as string);
      expect(body.limit).toBe(1000);
    });
  });

  describe('URL resolution', () => {
    it('should use custom URL from env var', async () => {
      process.env.NEXT_PUBLIC_JELLYFIN_BRIDGE_URL = 'http://custom-jellyfin:8093';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);

      await jellyfinSearch('test');

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('http://custom-jellyfin:8093');
    });

    it('should strip trailing slash from URL', async () => {
      process.env.NEXT_PUBLIC_JELLYFIN_BRIDGE_URL = 'http://localhost:8093/';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);

      await jellyfinSearch('test');

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('http://localhost:8093/jellyfin/search?');
    });
  });

  describe('Error handling', () => {
    it('should handle network errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(
        new Error('Network error')
      );

      const result = await jellyfinSearch('test');

      expect(result.ok).toBe(false);
    });

    it('should handle timeout errors', async () => {
      const abortError = new Error('Aborted') as Error & { name: string };
      abortError.name = 'AbortError';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(abortError);

      const result = await jellyfinSearch('test');

      expect(result.ok).toBe(false);
    });
  });
});
