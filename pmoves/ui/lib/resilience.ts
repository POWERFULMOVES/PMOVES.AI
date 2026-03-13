/**
 * @fileoverview Resilience patterns for API clients
 *
 * Provides:
 * - Exponential backoff retry logic
 * - Circuit breaker for preventing cascade failures
 * - Request timeout utilities
 *
 * @module resilience
 */

import { logError } from './errorUtils';
import { ErrorIds } from './constants/errorIds';

/**
 * Retry configuration options.
 */
export interface RetryOptions {
  /** Maximum number of retry attempts (default: 3) */
  maxAttempts?: number;
  /** Initial delay in milliseconds (default: 100) */
  initialDelay?: number;
  /** Backoff multiplier (default: 2) */
  backoffMultiplier?: number;
  /** Maximum delay in milliseconds (default: 10000) */
  maxDelay?: number;
  /** Function to determine if an error is retryable */
  retryable?: (error: unknown) => boolean;
  /** Optional callback for retry attempts */
  onRetry?: (attempt: number, error: unknown) => void;
}

/**
 * Default retry options.
 */
const DEFAULT_RETRY_OPTIONS: Required<RetryOptions> = {
  maxAttempts: 3,
  initialDelay: 100,
  backoffMultiplier: 2,
  maxDelay: 10000,
  retryable: (error) => {
    // Retry on network errors and 5xx server errors
    if (error instanceof Error) {
      // Network errors (no response)
      if (error.message.includes('fetch') || error.message.includes('network')) {
        return true;
      }
      // AbortError (timeout) - may be retryable depending on context
      if (error.name === 'AbortError') {
        return false; // Don't retry timeouts by default
      }
    }
    return false;
  },
  onRetry: () => {},
};

/**
 * Circuit breaker states.
 */
type CircuitState = 'closed' | 'open' | 'half-open';

/**
 * Circuit breaker configuration.
 */
export interface CircuitBreakerOptions {
  /** Failure threshold before opening circuit (default: 5) */
  failureThreshold?: number;
  /** Timeout in milliseconds before attempting half-open (default: 60000) */
  resetTimeout?: number;
  /** Success threshold to close circuit in half-open state (default: 2) */
  successThreshold?: number;
}

/**
 * Default circuit breaker options.
 */
const DEFAULT_CIRCUIT_OPTIONS: Required<CircuitBreakerOptions> = {
  failureThreshold: 5,
  resetTimeout: 60000,
  successThreshold: 2,
};

/**
 * Calculates delay for exponential backoff.
 *
 * @param attempt - Current attempt number (1-based)
 * @param options - Retry options
 * @returns Delay in milliseconds
 */
function calculateDelay(attempt: number, options: Required<RetryOptions>): number {
  const delay = options.initialDelay * Math.pow(options.backoffMultiplier, attempt - 1);
  return Math.min(delay, options.maxDelay);
}

/**
 * Sleep for a specified duration.
 *
 * @param ms - Milliseconds to sleep
 * @returns Promise that resolves after delay
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Executes a function with exponential backoff retry logic.
 *
 * @param fn - Function to execute
 * @param options - Retry configuration
 * @returns Promise with function result
 *
 * @example
 * ```typescript
 * const result = await retry(
 *   () => fetch('https://api.example.com/data'),
 *   { maxAttempts: 5, initialDelay: 200 }
 * );
 * ```
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const opts = { ...DEFAULT_RETRY_OPTIONS, ...options };

  let lastError: unknown;

  for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      // Check if this is the last attempt or if error is not retryable
      if (attempt >= opts.maxAttempts || !opts.retryable(error)) {
        throw error;
      }

      // Calculate delay and wait
      const delay = calculateDelay(attempt, opts);
      opts.onRetry(attempt, error);

      logError(
        `Retry attempt ${attempt}/${opts.maxAttempts} after ${delay}ms delay`,
        error instanceof Error ? error : new Error(String(error)),
        'warning',
        {
          errorId: ErrorIds.NETWORK_TIMEOUT,
          component: 'resilience',
          action: 'retry',
          attempt,
          maxAttempts: opts.maxAttempts,
        }
      );

      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * Circuit breaker implementation for preventing cascade failures.
 *
 * Tracks failures and opens the circuit when threshold is reached,
 * blocking requests until the reset timeout expires.
 *
 * @example
 * ```typescript
 * const breaker = new CircuitBreaker({ failureThreshold: 5 });
 * const result = await breaker.execute(() => fetch('https://api.example.com/data'));
 * ```
 */
export class CircuitBreaker {
  private state: CircuitState = 'closed';
  private failureCount = 0;
  private successCount = 0;
  private lastFailureTime = 0;
  private nextAttemptTime = 0;
  private readonly mergedOptions: Required<CircuitBreakerOptions>;

  constructor(options: CircuitBreakerOptions = {}) {
    this.mergedOptions = { ...DEFAULT_CIRCUIT_OPTIONS, ...options };
  }

  /**
   * Executes a function with circuit breaker protection.
   *
   * @param fn - Function to execute
   * @returns Promise with function result
   * @throws Error if circuit is open or function fails
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    // Check if we should attempt to reset the circuit
    if (this.state === 'open' && Date.now() >= this.nextAttemptTime) {
      this.state = 'half-open';
      this.successCount = 0;
    }

    // Fail fast if circuit is open
    if (this.state === 'open') {
      const error = new Error(
        'Circuit breaker is OPEN. Blocking request to prevent cascade failure.'
      );
      (error as any).code = 'CIRCUIT_OPEN';
      throw error;
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  /**
   * Handles successful execution.
   */
  private onSuccess(): void {
    this.failureCount = 0;

    if (this.state === 'half-open') {
      this.successCount++;
      if (this.successCount >= this.mergedOptions.successThreshold) {
        this.state = 'closed';
        this.successCount = 0;
      }
    }
  }

  /**
   * Handles failed execution.
   */
  private onFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.failureCount >= this.mergedOptions.failureThreshold) {
      this.state = 'open';
      this.nextAttemptTime = Date.now() + this.mergedOptions.resetTimeout;

      logError(
        `Circuit breaker OPEN after ${this.failureCount} failures`,
        new Error('Circuit breaker opened'),
        'warning',
        {
          errorId: ErrorIds.NETWORK_CONNECTION_REFUSED,
          component: 'resilience',
          action: 'circuit-breaker',
          state: this.state,
          failureCount: this.failureCount,
        }
      );
    }
  }

  /**
   * Gets the current circuit state.
   */
  getState(): CircuitState {
    return this.state;
  }

  /**
   * Gets the current failure count.
   */
  getFailureCount(): number {
    return this.failureCount;
  }

  /**
   * Manually resets the circuit breaker to closed state.
   */
  reset(): void {
    this.state = 'closed';
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = 0;
    this.nextAttemptTime = 0;
  }

  /**
   * Gets diagnostic information about the circuit breaker.
   */
  getDiagnostics(): {
    state: CircuitState;
    failureCount: number;
    successCount: number;
    lastFailureTime: number;
    nextAttemptTime: number;
  } {
    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime,
      nextAttemptTime: this.nextAttemptTime,
    };
  }
}

/**
 * Creates a fetch wrapper with retry and circuit breaker.
 *
 * @param url - URL to fetch
 * @param init - Fetch init options
 * @param options - Resilience options
 * @returns Promise with fetch response
 *
 * @example
 * ```typescript
 * const response = await resilientFetch(
 *   'https://api.example.com/data',
 *   { method: 'GET' },
 *   { retry: { maxAttempts: 3 }, circuitBreaker: { failureThreshold: 5 } }
 * );
 * ```
 */
export async function resilientFetch(
  url: string,
  init?: RequestInit,
  options?: {
    retry?: RetryOptions;
    circuitBreaker?: CircuitBreakerOptions & { breaker?: CircuitBreaker };
  }
): Promise<Response> {
  const circuitBreaker =
    options?.circuitBreaker?.breaker ||
    new CircuitBreaker(options?.circuitBreaker);

  return circuitBreaker.execute(() =>
    retry(
      () =>
        fetch(url, {
          ...init,
          // Add timeout via AbortSignal if not provided
          signal: init?.signal || AbortSignal.timeout(30000),
        }),
      options?.retry
    )
  );
}

/**
 * Map of circuit breakers for different services.
 */
const circuitBreakers = new Map<string, CircuitBreaker>();

/**
 * Gets or creates a circuit breaker for a specific service.
 *
 * @param serviceKey - Service identifier
 * @param options - Circuit breaker options
 * @returns Circuit breaker instance
 */
export function getCircuitBreaker(
  serviceKey: string,
  options?: CircuitBreakerOptions
): CircuitBreaker {
  if (!circuitBreakers.has(serviceKey)) {
    circuitBreakers.set(serviceKey, new CircuitBreaker(options));
  }
  return circuitBreakers.get(serviceKey)!;
}

/**
 * Resets a specific circuit breaker.
 *
 * @param serviceKey - Service identifier
 */
export function resetCircuitBreaker(serviceKey: string): void {
  const breaker = circuitBreakers.get(serviceKey);
  if (breaker) {
    breaker.reset();
  }
}

/**
 * Gets diagnostic information for all circuit breakers.
 *
 * @returns Map of service keys to diagnostics
 */
export function getCircuitBreakerDiagnostics(): Record<
  string,
  ReturnType<CircuitBreaker['getDiagnostics']>
> {
  const diagnostics: Record<
    string,
    ReturnType<CircuitBreaker['getDiagnostics']>
  > = {};

  for (const [key, breaker] of circuitBreakers.entries()) {
    diagnostics[key] = breaker.getDiagnostics();
  }

  return diagnostics;
}
