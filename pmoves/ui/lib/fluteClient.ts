/**
 * Flute Gateway Client
 *
 * Provides HTTP and WebSocket interfaces to the Flute-Gateway voice service.
 * Supports both synchronous TTS synthesis and real-time streaming.
 *
 * @see .claude/context/flute-gateway.md for API reference
 */

export interface SynthesizeOptions {
  voice?: string;
  speed?: number;
  pitch?: number;
  emotion?: string;
}

export interface FluteSession {
  sessionId: string;
  createdAt: Date;
}

/**
 * Client for Flute-Gateway voice communication layer.
 *
 * Usage:
 * ```typescript
 * const flute = new FluteClient();
 *
 * // Synchronous synthesis
 * const audio = await flute.synthesize('Hello world');
 *
 * // Real-time streaming
 * flute.connect((audioData) => {
 *   // Handle streaming audio chunks
 * });
 * ```
 */
export class FluteClient {
  private ws: WebSocket | null = null;
  private readonly httpUrl: string;
  private readonly wsUrl: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;

  constructor(options?: { httpUrl?: string; wsUrl?: string }) {
    // Use environment variables with fallbacks for local development
    this.httpUrl = options?.httpUrl
      || process.env.NEXT_PUBLIC_FLUTE_GATEWAY_URL
      || 'http://localhost:8055';
    this.wsUrl = options?.wsUrl
      || process.env.NEXT_PUBLIC_FLUTE_WS_URL
      || 'ws://localhost:8056';
  }

  /**
   * Synthesize text to speech using prosodic synthesis.
   * Returns raw audio data as ArrayBuffer (WAV format).
   */
  async synthesize(text: string, options?: SynthesizeOptions): Promise<ArrayBuffer> {
    const response = await fetch(`${this.httpUrl}/v1/voice/synthesize/prosodic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        voice: options?.voice,
        speed: options?.speed,
        pitch: options?.pitch,
        emotion: options?.emotion,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Flute synthesis failed: ${response.status} - ${error}`);
    }

    return response.arrayBuffer();
  }

  /**
   * Check if Flute Gateway is healthy.
   */
  async isHealthy(): Promise<boolean> {
    try {
      const response = await fetch(`${this.httpUrl}/healthz`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Connect to WebSocket for real-time streaming.
   *
   * @param onMessage - Callback for incoming audio chunks
   * @param onError - Optional error handler
   * @param onClose - Optional close handler
   */
  connect(
    onMessage: (data: ArrayBuffer) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void,
  ): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.warn('FluteClient: Already connected');
      return;
    }

    this.ws = new WebSocket(this.wsUrl);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      console.log('FluteClient: WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        onMessage(event.data);
      }
    };

    this.ws.onerror = (error) => {
      console.error('FluteClient: WebSocket error', error);
      onError?.(error);
    };

    this.ws.onclose = (event) => {
      console.log('FluteClient: WebSocket closed', event.code, event.reason);
      onClose?.(event);

      // Auto-reconnect on unexpected close
      if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`FluteClient: Reconnecting (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(onMessage, onError, onClose), 1000 * this.reconnectAttempts);
      }
    };
  }

  /**
   * Send text for streaming synthesis.
   * Must be connected first via connect().
   */
  sendText(text: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('FluteClient: Not connected. Call connect() first.');
    }
    this.ws.send(JSON.stringify({ type: 'synthesize', text }));
  }

  /**
   * Disconnect WebSocket connection.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  /**
   * Check if WebSocket is connected.
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

/**
 * Play audio data through Web Audio API.
 * Utility function for client-side audio playback.
 */
export async function playAudio(audioData: ArrayBuffer): Promise<void> {
  const audioContext = new AudioContext();
  const audioBuffer = await audioContext.decodeAudioData(audioData);
  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioContext.destination);
  source.start(0);

  return new Promise((resolve) => {
    source.onended = () => {
      audioContext.close();
      resolve();
    };
  });
}

// Singleton instance for convenience
let defaultClient: FluteClient | null = null;

export function getFluteClient(): FluteClient {
  if (!defaultClient) {
    defaultClient = new FluteClient();
  }
  return defaultClient;
}
