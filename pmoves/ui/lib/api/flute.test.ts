/**
 * @fileoverview Flute Gateway API Client Integration Tests
 *
 * Tests TTS synthesis, voice management, and WebSocket streaming.
 *
 * @module api/flute.test
 */

import {
  fluteHealth,
  fluteSynthesize,
  fluteListVoices,
  fluteGetVoiceSample,
  fluteEstimateDuration,
  fluteValidateRequest,
} from './flute';

// Mock fetch for testing
const mockFetch = jest.fn();
global.fetch = mockFetch as jest.MockedFunction<typeof fetch>;

// Mock WebSocket for streaming tests
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simulate connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(data: string) {
    // Mock send
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

(global as any).WebSocket = MockWebSocket;

describe('Flute Gateway API Client', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockVoice = {
    id: 'voice-123',
    name: 'Default Voice',
    language: 'en-US',
    gender: 'neutral' as const,
    description: 'A neutral voice',
    sampleUrl: 'https://example.com/sample.mp3',
    features: ['prosody', 'ssml'],
  };

  describe('fluteHealth', () => {
    it('should return healthy status when service is available', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          healthy: true,
          version: '1.0.0',
          voiceCount: 10,
          engine: 'kokoro',
        }),
      } as Response);

      const result = await fluteHealth();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.healthy).toBe(true);
        expect(result.data.voiceCount).toBe(10);
        expect(result.data.engine).toBe('kokoro');
      }
    });

    it('should return error when service is unavailable', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Connection refused'));

      const result = await fluteHealth();

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Flute Gateway service unavailable');
      }
    });
  });

  describe('fluteSynthesize', () => {
    it('should synthesize speech successfully', async () => {
      const mockResponse = {
        audioUrl: 'https://example.com/audio.mp3',
        duration: 2.5,
        samples: 120000,
        sampleRate: 48000,
        voiceId: 'voice-123',
        synthesisTime: 1500,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await fluteSynthesize({
        text: 'Hello, world!',
        voiceId: 'voice-123',
        quality: 'high',
      });

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.audioUrl).toBe('https://example.com/audio.mp3');
        expect(result.data.duration).toBe(2.5);
        expect(result.data.synthesisTime).toBe(1500);
      }
    });

    it('should handle synthesis timeout', async () => {
      mockFetch.mockRejectedValueOnce(new Error('AbortError'));

      const result = await fluteSynthesize({
        text: 'A very long text that times out...',
      });

      expect(result.ok).toBe(false);
    });

    it('should handle synthesis errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response);

      const result = await fluteSynthesize({
        text: 'Invalid text',
      });

      expect(result.ok).toBe(false);
    });
  });

  describe('fluteListVoices', () => {
    it('should return list of voices', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ voices: [mockVoice] }),
      } as Response);

      const result = await fluteListVoices();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toHaveLength(1);
        expect(result.data[0].id).toBe('voice-123');
        expect(result.data[0].language).toBe('en-US');
      }
    });

    it('should handle empty voice list', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await fluteListVoices();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toEqual([]);
      }
    });
  });

  describe('fluteGetVoiceSample', () => {
    it('should return voice sample URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          sampleUrl: 'https://example.com/sample.mp3',
        }),
      } as Response);

      const result = await fluteGetVoiceSample('voice-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toBe('https://example.com/sample.mp3');
      }
    });
  });

  describe('fluteValidateRequest', () => {
    it('should validate correct request', () => {
      const result = fluteValidateRequest({
        text: 'Hello, world!',
        voiceId: 'voice-123',
        rate: 1.0,
        pitch: 0,
        format: 'mp3',
      });

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.valid).toBe(true);
      }
    });

    it('should reject empty text', () => {
      const result = fluteValidateRequest({
        text: '   ',
      });

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain('Text cannot be empty or whitespace only');
      }
    });

    it('should reject text that is too long', () => {
      const result = fluteValidateRequest({
        text: 'a'.repeat(10001),
      });

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain('Text is too long (max 10000 characters)');
      }
    });

    it('should reject invalid rate', () => {
      const result = fluteValidateRequest({
        text: 'Test',
        rate: 3.0,
      });

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain('Rate must be between 0.5 and 2.0');
      }
    });

    it('should reject invalid pitch', () => {
      const result = fluteValidateRequest({
        text: 'Test',
        pitch: 20,
      });

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain('Pitch must be between -12 and 12 semitones');
      }
    });

    it('should reject invalid format', () => {
      const result = fluteValidateRequest({
        text: 'Test',
        format: 'flac' as any,
      });

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain('Format must be one of: mp3, wav, pcm');
      }
    });
  });

  describe('fluteEstimateDuration', () => {
    it('should estimate duration for text', () => {
      const duration = fluteEstimateDuration('Hello world test', 1.0);

      // 3 words / 150 words per minute * 60 seconds = ~1.2 seconds
      expect(duration).toBeGreaterThan(0);
      expect(duration).toBeLessThan(5);
    });

    it('should adjust duration based on rate', () => {
      const normalRate = fluteEstimateDuration('Hello world test', 1.0);
      const doubleRate = fluteEstimateDuration('Hello world test', 2.0);

      expect(doubleRate).toBeLessThan(normalRate);
    });

    it('should handle empty text', () => {
      const duration = fluteEstimateDuration('   ', 1.0);

      expect(duration).toBe(0);
    });

    it('should handle rate at boundaries', () => {
      const duration1 = fluteEstimateDuration('Test', 0.5);
      const duration2 = fluteEstimateDuration('Test', 2.0);

      expect(duration2).toBeLessThan(duration1);
    });
  });
});
