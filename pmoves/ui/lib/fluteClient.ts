/**
 * Flute Gateway Client
 *
 * Provides HTTP and WebSocket interfaces to the Flute-Gateway voice service.
 * Supports both synchronous TTS synthesis and real-time streaming.
 *
 * Service URL resolution via PMOVES service discovery:
 * 1. NEXT_PUBLIC_FLUTE_GATEWAY_URL environment variable (explicit override)
 * 2. Service catalog (Supabase) via service registry
 * 3. Docker DNS fallback (flute-gateway:8055)
 *
 * No authentication required for basic synthesis operations.
 *
 * @see .claude/context/flute-gateway.md for API reference
 *
 * @example
 * ```typescript
 * const flute = new FluteClient();
 *
 * // Synchronous synthesis
 * const audio = await flute.synthesize('Hello world');
 *
 * // Session-based streaming
 * const session = await flute.createSession();
 * flute.connectWithSession(session, (audioData) => {
 *   // Handle streaming audio chunks
 * });
 * ```
 */

import { getServiceUrl } from './serviceDiscovery';

export interface SynthesizeOptions {
  voice?: string;
  speed?: number;
  pitch?: number;
  emotion?: string;
}

/**
 * Represents a Flute-Gateway voice session.
 * Sessions provide dedicated WebSocket connections for real-time streaming.
 */
export interface FluteSession {
  /** Unique session identifier */
  sessionId: string;
  /** Dedicated WebSocket URL for this session */
  websocketUrl: string;
  /** Session creation timestamp */
  createdAt: Date;
}

/**
 * Client for Flute-Gateway voice communication layer.
 *
 * Provides both synchronous TTS synthesis and real-time WebSocket streaming.
 * Session management is recommended for production use with multiple
 * concurrent voice interactions.
 *
 * Service URLs are resolved lazily on first use via PMOVES service discovery.
 */
export class FluteClient {
  private ws: WebSocket | null = null;
  private httpUrl?: string;
  private wsUrl?: string;
  private serviceSlug = 'flute-gateway';
  private httpPort = 8055;
  private wsPort = 8056;
  private urlResolved = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private currentCallbacks: {
    onMessage?: (data: ArrayBuffer) => void;
    onError?: (error: Event) => void;
    onClose?: (event: CloseEvent) => void;
    onReconnectExhausted?: () => void;
  } = {};

  constructor(options?: { httpUrl?: string; wsUrl?: string }) {
    // Use explicit URLs if provided, otherwise resolve via service discovery
    if (options?.httpUrl) {
      this.httpUrl = options.httpUrl.replace(/\/$/, '');
      this.urlResolved = true;
    }
    if (options?.wsUrl) {
      this.wsUrl = options.wsUrl.replace(/\/$/, '');
    }
    // Check environment variables for explicit override
    if (!this.urlResolved) {
      const envHttpUrl = process.env.NEXT_PUBLIC_FLUTE_GATEWAY_URL;
      const envWsUrl = process.env.NEXT_PUBLIC_FLUTE_WS_URL;
      if (envHttpUrl) {
        this.httpUrl = envHttpUrl.replace(/\/$/, '');
        this.urlResolved = true;
      }
      if (envWsUrl) {
        this.wsUrl = envWsUrl.replace(/\/$/, '');
      }
    }
  }

  /**
   * Resolve service URLs using PMOVES service discovery.
   * Called lazily on first API use to avoid blocking constructor.
   */
  private async resolveUrls(): Promise<void> {
    if (this.urlResolved) return;

    // Resolve HTTP URL
    if (!this.httpUrl) {
      this.httpUrl = await getServiceUrl({
        slug: this.serviceSlug,
        defaultPort: this.httpPort,
      });
    }

    // Resolve WebSocket URL (convert HTTP to WS protocol)
    if (!this.wsUrl && this.httpUrl) {
      this.wsUrl = this.httpUrl.replace(/^http/, 'ws').replace(':8055', ':8056');
    }

    this.urlResolved = true;
  }

  /**
   * Get the HTTP URL, resolving via service discovery if needed.
   */
  private async getHttpUrl(): Promise<string> {
    if (!this.urlResolved) {
      await this.resolveUrls();
    }
    return this.httpUrl!;
  }

  /**
   * Get the WebSocket URL, resolving via service discovery if needed.
   */
  private async getWsUrl(): Promise<string> {
    if (!this.urlResolved) {
      await this.resolveUrls();
    }
    return this.wsUrl!;
  }

  /**
   * Synthesize text to speech using prosodic synthesis.
   * Returns raw audio data as ArrayBuffer (WAV format).
   *
   * @param text - The text to synthesize
   * @param options - Optional synthesis parameters (voice, speed, pitch, emotion)
   * @returns ArrayBuffer containing WAV audio data
   * @throws {Error} If synthesis request fails or network error occurs
   */
  async synthesize(text: string, options?: SynthesizeOptions): Promise<ArrayBuffer> {
    const httpUrl = await this.getHttpUrl();
    const response = await fetch(`${httpUrl}/v1/voice/synthesize/prosodic`, {
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
   * Create a new voice session for real-time streaming.
   * Sessions provide dedicated WebSocket connections and are recommended
   * for production use with multiple concurrent interactions.
   *
   * @returns FluteSession with session ID and dedicated WebSocket URL
   * @throws {Error} If session creation fails
   */
  async createSession(): Promise<FluteSession> {
    const httpUrl = await this.getHttpUrl();
    const response = await fetch(`${httpUrl}/v1/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Flute session creation failed: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return {
      sessionId: data.session_id,
      websocketUrl: data.websocket_url,
      createdAt: new Date(data.created_at),
    };
  }

  /**
   * Check if Flute Gateway is healthy.
   *
   * @returns true if gateway is healthy, false otherwise
   */
  async isHealthy(): Promise<boolean> {
    try {
      const httpUrl = await this.getHttpUrl();
      const response = await fetch(`${httpUrl}/healthz`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch (error) {
      console.warn('FluteClient: Health check failed', error);
      return false;
    }
  }

  /**
   * Connect to WebSocket for real-time streaming using default endpoint.
   *
   * For production use with multiple concurrent sessions, prefer
   * createSession() + connectWithSession() for dedicated connections.
   *
   * @param onMessage - Callback for incoming audio chunks
   * @param onError - Optional error handler
   * @param onClose - Optional close handler
   * @param onReconnectExhausted - Optional callback when max reconnection attempts exhausted
   */
  async connect(
    onMessage: (data: ArrayBuffer) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void,
    onReconnectExhausted?: () => void,
  ): Promise<void> {
    const wsUrl = await this.getWsUrl();
    this.connectToUrl(wsUrl, onMessage, onError, onClose, onReconnectExhausted);
  }

  /**
   * Connect to WebSocket using a dedicated session.
   *
   * @param session - FluteSession obtained from createSession()
   * @param onMessage - Callback for incoming audio chunks
   * @param onError - Optional error handler
   * @param onClose - Optional close handler
   * @param onReconnectExhausted - Optional callback when max reconnection attempts exhausted
   */
  connectWithSession(
    session: FluteSession,
    onMessage: (data: ArrayBuffer) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void,
    onReconnectExhausted?: () => void,
  ): void {
    this.connectToUrl(session.websocketUrl, onMessage, onError, onClose, onReconnectExhausted);
  }

  /**
   * Internal method to connect to a WebSocket URL.
   */
  private connectToUrl(
    url: string,
    onMessage: (data: ArrayBuffer) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void,
    onReconnectExhausted?: () => void,
  ): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.warn('FluteClient: Already connected');
      return;
    }

    // Store callbacks for potential reconnection
    this.currentCallbacks = { onMessage, onError, onClose, onReconnectExhausted };

    this.ws = new WebSocket(url);
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
        setTimeout(
          () => this.connectToUrl(url, onMessage, onError, onClose, onReconnectExhausted),
          1000 * this.reconnectAttempts,
        );
      } else if (!event.wasClean && this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('FluteClient: Max reconnection attempts exhausted');
        onReconnectExhausted?.();
      }
    };
  }

  /**
   * Send text for streaming synthesis.
   * Must be connected first via connect() or connectWithSession().
   *
   * @param text - Text to synthesize
   * @param voice - Optional voice identifier
   * @throws {Error} If not connected to WebSocket
   */
  sendText(text: string, voice?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('FluteClient: Not connected. Call connect() or connectWithSession() first.');
    }
    this.ws.send(JSON.stringify({ type: 'text', text, voice }));
  }

  /**
   * Disconnect WebSocket connection.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.currentCallbacks = {};
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
 *
 * @warning Browser-only - AudioContext not available in Node.js/SSR
 * @param audioData - ArrayBuffer containing audio data (WAV format)
 * @throws {Error} If audio decoding fails or AudioContext unavailable
 */
export async function playAudio(audioData: ArrayBuffer): Promise<void> {
  const audioContext = new AudioContext();
  try {
    const audioBuffer = await audioContext.decodeAudioData(audioData);
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    source.start(0);

    return new Promise((resolve, reject) => {
      source.onended = () => {
        audioContext.close();
        resolve();
      };
      // Note: AudioBufferSourceNode doesn't have onerror, but decode errors
      // are caught by the outer try/catch
    });
  } catch (error) {
    await audioContext.close();
    throw error;
  }
}

// Singleton instance for convenience
let defaultClient: FluteClient | null = null;

/**
 * Get the default FluteClient singleton instance.
 * Useful for simple use cases without session management.
 *
 * @returns Shared FluteClient instance
 */
export function getFluteClient(): FluteClient {
  if (!defaultClient) {
    defaultClient = new FluteClient();
  }
  return defaultClient;
}
