/**
 * @fileoverview Flute Gateway API Client for PMOVES UI
 *
 * Integrates with Flute Gateway for:
 * - Prosodic text-to-speech synthesis
 * - WebSocket streaming for real-time audio
 * - Voice management and discovery
 * - Service health monitoring
 *
 * @module api/flute
 */

import { logError, Result, ok, err, getErrorMessage } from '../errorUtils';
import { ErrorIds } from '../constants/errorIds';

/**
 * Service configuration for Flute Gateway.
 */
const FLUTE_SERVICE_CONFIG = {
  slug: 'flute-gateway',
  defaultPort: 8055,
  envVar: 'NEXT_PUBLIC_FLUTE_GATEWAY_URL',
  wsPort: 8056,
  wsEnvVar: 'NEXT_PUBLIC_FLUTE_WS_URL',
} as const;

const FLUTE_TIMEOUT = 60000; // 60 seconds for TTS synthesis

/**
 * Resolves Flute Gateway HTTP URL from environment or default.
 */
function getFluteUrl(): string {
  return (
    process.env.NEXT_PUBLIC_FLUTE_GATEWAY_URL ||
    process.env.FLUTE_GATEWAY_URL ||
    `http://localhost:${FLUTE_SERVICE_CONFIG.defaultPort}`
  ).replace(/\/$/, '');
}

/**
 * Resolves Flute Gateway WebSocket URL from environment or default.
 */
function getFluteWsUrl(): string {
  const envWs =
    process.env.NEXT_PUBLIC_FLUTE_WS_URL || process.env.FLUTE_WS_URL;
  if (envWs) {
    return envWs.replace(/\/$/, '');
  }

  // Derive WS URL from HTTP URL
  const httpUrl = getFluteUrl();
  return httpUrl.replace(/^http/, 'ws').replace(':8055', ':8056');
}

/**
 * Synthesis quality levels.
 */
export type SynthesisQuality = 'low' | 'medium' | 'high';

/**
 * Voice profile definition.
 */
export interface FluteVoice {
  /** Unique voice ID */
  id: string;
  /** Voice display name */
  name: string;
  /** Voice language code */
  language: string;
  /** Voice gender */
  gender?: 'male' | 'female' | 'neutral';
  /** Voice description */
  description?: string;
  /** Sample audio URL */
  sampleUrl?: string;
  /** Supported features */
  features?: string[];
}

/**
 * Prosodic synthesis request.
 */
export interface ProsodicSynthesisRequest {
  /** Text to synthesize */
  text: string;
  /** Voice ID to use */
  voiceId?: string;
  /** Synthesis quality */
  quality?: SynthesisQuality;
  /** Speech rate multiplier (0.5 - 2.0) */
  rate?: number;
  /** Pitch adjustment in semitones (-12 - 12) */
  pitch?: number;
  /** Output format (mp3, wav, pcm) */
  format?: 'mp3' | 'wav' | 'pcm';
}

/**
 * Synthesis response with audio data.
 */
export interface SynthesisResponse {
  /** Generated audio URL */
  audioUrl: string;
  /** Audio duration in seconds */
  duration: number;
  /** Number of samples */
  samples: number;
  /** Sample rate */
  sampleRate: number;
  /** Used voice ID */
  voiceId?: string;
  /** Synthesis time in milliseconds */
  synthesisTime: number;
}

/**
 * WebSocket synthesis message types.
 */
export type WSMessage =
  | { type: 'start'; requestId: string }
  | { type: 'progress'; progress: number; audioChunk?: string }
  | { type: 'complete'; audioUrl: string; duration: number }
  | { type: 'error'; error: string };

/**
 * WebSocket synthesis options.
 */
export interface WSSynthesisOptions extends ProsodicSynthesisRequest {
  /** Called when synthesis starts */
  onStart?: () => void;
  /** Called on progress updates (0-100) */
  onProgress?: (progress: number, audioChunk?: ArrayBuffer) => void;
  /** Called when synthesis completes */
  onComplete?: (audioUrl: string, duration: number) => void;
  /** Called on error */
  onError?: (error: string) => void;
}

/**
 * Health check response.
 */
export interface FluteHealth {
  /** Service health status */
  healthy: boolean;
  /** Service version */
  version?: string;
  /** Available voice count */
  voiceCount?: number;
  /** Backend engine (kokoro, xtts, etc.) */
  engine?: string;
}

/**
 * Synthesizes speech using prosodic synthesis via HTTP.
 *
 * @param request - Synthesis request
 * @returns Result with synthesis response or error message
 *
 * @example
 * ```typescript
 * const result = await fluteSynthesize({
 *   text: 'Hello, world!',
 *   voiceId: 'default',
 *   quality: 'high'
 * });
 * if (result.ok) {
 *   const audio = new Audio(result.data.audioUrl);
 *   audio.play();
 * }
 * ```
 */
export async function fluteSynthesize(
  request: ProsodicSynthesisRequest
): Promise<Result<SynthesisResponse, string>> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FLUTE_TIMEOUT);

    const response = await fetch(`${getFluteUrl()}/v1/voice/synthesize/prosodic`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Flute synthesis failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.FLUTE_SYNTHESIS_FAILED,
          component: 'flute',
          action: 'synthesize',
          textLength: request.text.length,
        }
      );
      return err(message);
    }

    const data = (await response.json()) as SynthesisResponse;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Flute synthesis error', error, 'error', {
      errorId: ErrorIds.FLUTE_SYNTHESIS_FAILED,
      component: 'flute',
      action: 'synthesize',
    });
    return err(message);
  }
}

/**
 * Synthesizes speech using WebSocket streaming.
 *
 * @param request - Synthesis request
 * @param options - Callback options
 * @returns Result with WebSocket cleanup function or error message
 *
 * @example
 * ```typescript
 * const result = await fluteSynthesizeStream(
 *   { text: 'Hello, world!', voiceId: 'default' },
 *   {
 *     onProgress: (p) => console.log(`Progress: ${p}%`),
 *     onComplete: (url) => console.log(`Done: ${url}`)
 *   }
 * );
 * ```
 */
export async function fluteSynthesizeStream(
  request: ProsodicSynthesisRequest,
  options: WSSynthesisOptions
): Promise<Result<() => void, string>> {
  try {
    // First, initiate the synthesis via HTTP to get a request ID
    const initiateResponse = await fetch(
      `${getFluteUrl()}/v1/voice/synthesize/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!initiateResponse.ok) {
      return err('Failed to initiate stream synthesis');
    }

    const { requestId } = (await initiateResponse.json()) as { requestId: string };

    // Connect via WebSocket for streaming
    const wsUrl = `${getFluteWsUrl()}/v1/voice/stream/${encodeURIComponent(requestId)}`;
    const ws = new WebSocket(wsUrl);

    let cleanupCalled = false;
    const cleanup = () => {
      cleanupCalled = true;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };

    ws.onopen = () => {
      if (!cleanupCalled) {
        options.onStart?.();
      }
    };

    ws.onmessage = (event) => {
      if (cleanupCalled) return;

      try {
        const message = JSON.parse(event.data) as WSMessage;

        switch (message.type) {
          case 'start':
            // Synthesis started
            break;
          case 'progress':
            options.onProgress?.(
              message.progress,
              message.audioChunk
                ? Uint8Array.from(atob(message.audioChunk), (c) => c.charCodeAt(0)).buffer
                : undefined
            );
            break;
          case 'complete':
            options.onComplete?.(message.audioUrl, message.duration);
            cleanup();
            break;
          case 'error':
            options.onError?.(message.error);
            cleanup();
            break;
        }
      } catch (err) {
        logError('Flute WebSocket message parse error', err, 'warning', {
          errorId: ErrorIds.FLUTE_WEBSOCKET_FAILED,
          component: 'flute',
          action: 'stream',
        });
      }
    };

    ws.onerror = (error) => {
      if (!cleanupCalled) {
        logError('Flute WebSocket error', error, 'error', {
          errorId: ErrorIds.FLUTE_WEBSOCKET_FAILED,
          component: 'flute',
          action: 'stream',
        });
        options.onError?.('WebSocket connection error');
      }
    };

    ws.onclose = () => {
      // Cleanup handled by individual message handlers
    };

    return ok(cleanup);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Flute stream synthesis error', error, 'error', {
      errorId: ErrorIds.FLUTE_WEBSOCKET_FAILED,
      component: 'flute',
      action: 'stream',
    });
    return err(message);
  }
}

/**
 * Lists available voices.
 *
 * @returns Result with voice list or error message
 */
export async function fluteListVoices(): Promise<Result<FluteVoice[], string>> {
  try {
    const response = await fetch(`${getFluteUrl()}/v1/voices`, {
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Flute list voices failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.FLUTE_VOICE_LIST_FAILED,
          component: 'flute',
          action: 'list-voices',
        }
      );
      return err(message);
    }

    const data = (await response.json()) as { voices?: FluteVoice[] };
    return ok(data.voices ?? []);
  } catch (error) {
    logError('Flute list voices error', error, 'warning', {
      errorId: ErrorIds.FLUTE_VOICE_LIST_FAILED,
      component: 'flute',
      action: 'list-voices',
    });
    return err('Failed to list voices');
  }
}

/**
 * Gets a voice sample URL.
 *
 * @param voiceId - Voice ID
 * @returns Result with sample URL or error message
 */
export async function fluteGetVoiceSample(
  voiceId: string
): Promise<Result<string, string>> {
  try {
    const response = await fetch(
      `${getFluteUrl()}/v1/voices/${encodeURIComponent(voiceId)}/sample`,
      {
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!response.ok) {
      return err('Failed to get voice sample');
    }

    const data = (await response.json()) as { sampleUrl: string };
    return ok(data.sampleUrl);
  } catch (error) {
    logError('Flute get voice sample error', error, 'warning', {
      errorId: ErrorIds.FLUTE_VOICE_LIST_FAILED,
      component: 'flute',
      action: 'get-sample',
      voiceId,
    });
    return err('Failed to get voice sample');
  }
}

/**
 * Checks health status of Flute Gateway service.
 *
 * @returns Result with health status or error message
 */
export async function fluteHealth(): Promise<Result<FluteHealth, string>> {
  try {
    const response = await fetch(`${getFluteUrl()}/healthz`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return err('Flute Gateway health check failed');
    }

    const data = (await response.json()) as FluteHealth;
    return ok({ ...data, healthy: true });
  } catch (error) {
    logError('Flute health check error', error, 'warning', {
      errorId: ErrorIds.FLUTE_HEALTH_CHECK_FAILED,
      component: 'flute',
      action: 'health',
    });
    return err('Flute Gateway service unavailable');
  }
}

/**
 * Validates synthesis request parameters.
 *
 * @param request - Request to validate
 * @returns Result with validation result or error message
 */
export function fluteValidateRequest(
  request: ProsodicSynthesisRequest
): Result<{ valid: true }, { valid: false; errors: string[] }> {
  const errors: string[] = [];

  // Validate text
  if (!request.text || typeof request.text !== 'string') {
    errors.push('Text is required and must be a string');
  } else if (request.text.length > 10000) {
    errors.push('Text is too long (max 10000 characters)');
  } else if (request.text.trim().length === 0) {
    errors.push('Text cannot be empty or whitespace only');
  }

  // Validate rate
  if (request.rate !== undefined) {
    if (typeof request.rate !== 'number') {
      errors.push('Rate must be a number');
    } else if (request.rate < 0.5 || request.rate > 2.0) {
      errors.push('Rate must be between 0.5 and 2.0');
    }
  }

  // Validate pitch
  if (request.pitch !== undefined) {
    if (typeof request.pitch !== 'number') {
      errors.push('Pitch must be a number');
    } else if (request.pitch < -12 || request.pitch > 12) {
      errors.push('Pitch must be between -12 and 12 semitones');
    }
  }

  // Validate format
  if (
    request.format &&
    !['mp3', 'wav', 'pcm'].includes(request.format)
  ) {
    errors.push('Format must be one of: mp3, wav, pcm');
  }

  if (errors.length > 0) {
    return err({ valid: false, errors });
  }

  return ok({ valid: true });
}

/**
 * Estimates synthesis duration based on text length and rate.
 *
 * @param text - Text to synthesize
 * @param rate - Speech rate multiplier (default: 1.0)
 * @returns Estimated duration in seconds
 */
export function fluteEstimateDuration(
  text: string,
  rate: number = 1.0
): number {
  // Average reading speed: ~150 words per minute
  const words = text.trim().split(/\s+/).length;
  const baseMinutes = words / 150;
  const baseSeconds = baseMinutes * 60;

  // Adjust for rate
  return baseSeconds / Math.max(0.1, rate);
}
