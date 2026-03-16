/**
 * Unit tests for lib/resilience.ts
 *
 * Tests retry(), CircuitBreaker, and resilientFetch() — infrastructure-critical
 * patterns that protect against cascade failures.
 */

import { retry, CircuitBreaker, resilientFetch } from '../resilience';

// ---------------------------------------------------------------------------
// Polyfills for jsdom (lacks fetch API Response class)
// ---------------------------------------------------------------------------
if (typeof globalThis.Response === 'undefined') {
  globalThis.Response = class Response {
    readonly ok: boolean;
    readonly status: number;
    readonly statusText: string;
    readonly headers: Headers;
    private _body: string;
    constructor(body?: string | null, init?: { status?: number; statusText?: string }) {
      this._body = body ?? '';
      this.status = init?.status ?? 200;
      this.statusText = init?.statusText ?? 'OK';
      this.ok = this.status >= 200 && this.status < 300;
      this.headers = new Headers();
    }
    async text() { return this._body; }
    async json() { return JSON.parse(this._body); }
  } as unknown as typeof Response;
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock logError to prevent console noise in tests
jest.mock('../errorUtils', () => ({
  logError: jest.fn(),
}));

// ---------------------------------------------------------------------------
// retry()
// ---------------------------------------------------------------------------

describe('retry()', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('succeeds on first attempt', async () => {
    const fn = jest.fn().mockResolvedValue('ok');
    const result = await retry(fn, { maxAttempts: 3 });
    expect(result).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('retries on failure up to maxAttempts', async () => {
    const error = new Error('network fetch failed');
    const fn = jest.fn()
      .mockRejectedValueOnce(error)
      .mockRejectedValueOnce(error)
      .mockResolvedValue('success');

    // Use real timers for this test since we need actual async resolution
    jest.useRealTimers();

    const result = await retry(fn, {
      maxAttempts: 3,
      initialDelay: 1,
      retryable: () => true,
    });
    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('throws after exhausting all retries', async () => {
    jest.useRealTimers();
    const error = new Error('persistent network fetch failure');
    const fn = jest.fn().mockRejectedValue(error);

    await expect(
      retry(fn, {
        maxAttempts: 2,
        initialDelay: 1,
        retryable: () => true,
      })
    ).rejects.toThrow('persistent network fetch failure');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('does not retry non-retryable errors', async () => {
    const error = new Error('not retryable');
    const fn = jest.fn().mockRejectedValue(error);

    await expect(
      retry(fn, {
        maxAttempts: 3,
        retryable: () => false,
      })
    ).rejects.toThrow('not retryable');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('calls onRetry callback with attempt number and error', async () => {
    jest.useRealTimers();
    const error = new Error('network fetch fail');
    const onRetry = jest.fn();
    const fn = jest.fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue('ok');

    await retry(fn, {
      maxAttempts: 3,
      initialDelay: 1,
      retryable: () => true,
      onRetry,
    });

    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onRetry).toHaveBeenCalledWith(1, error);
  });

  it('respects backoff multiplier for delay calculation', async () => {
    jest.useRealTimers();
    const error = new Error('network fetch error');
    const onRetry = jest.fn();
    const fn = jest.fn()
      .mockRejectedValueOnce(error)
      .mockRejectedValueOnce(error)
      .mockResolvedValue('ok');

    const start = Date.now();
    await retry(fn, {
      maxAttempts: 3,
      initialDelay: 10,
      backoffMultiplier: 2,
      retryable: () => true,
      onRetry,
    });
    const elapsed = Date.now() - start;

    // Should have waited at least ~10ms + ~20ms = ~30ms (with some margin)
    expect(elapsed).toBeGreaterThanOrEqual(20);
    expect(fn).toHaveBeenCalledTimes(3);
  });
});

// ---------------------------------------------------------------------------
// CircuitBreaker
// ---------------------------------------------------------------------------

describe('CircuitBreaker', () => {
  it('starts in closed state', () => {
    const breaker = new CircuitBreaker();
    expect(breaker.getState()).toBe('closed');
    expect(breaker.getFailureCount()).toBe(0);
  });

  it('remains closed on successful executions', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 3 });
    const result = await breaker.execute(async () => 'ok');
    expect(result).toBe('ok');
    expect(breaker.getState()).toBe('closed');
  });

  it('opens after failure threshold reached', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 3, resetTimeout: 60000 });
    const error = new Error('fail');

    for (let i = 0; i < 3; i++) {
      await expect(breaker.execute(async () => { throw error; })).rejects.toThrow('fail');
    }

    expect(breaker.getState()).toBe('open');
    expect(breaker.getFailureCount()).toBe(3);
  });

  it('rejects immediately when open', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 2, resetTimeout: 60000 });
    const error = new Error('fail');

    // Open the circuit
    for (let i = 0; i < 2; i++) {
      await expect(breaker.execute(async () => { throw error; })).rejects.toThrow('fail');
    }
    expect(breaker.getState()).toBe('open');

    // Subsequent calls should fail immediately with circuit breaker error
    await expect(breaker.execute(async () => 'should not run')).rejects.toThrow(
      'Circuit breaker is OPEN'
    );
  });

  it('transitions to half-open after reset timeout', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 2, resetTimeout: 100 });
    const error = new Error('fail');

    // Open the circuit
    for (let i = 0; i < 2; i++) {
      await expect(breaker.execute(async () => { throw error; })).rejects.toThrow();
    }
    expect(breaker.getState()).toBe('open');

    // Wait for reset timeout
    await new Promise((r) => setTimeout(r, 150));

    // Next execution should transition to half-open and attempt the call
    const result = await breaker.execute(async () => 'recovered');
    expect(result).toBe('recovered');
    // After 1 success (below successThreshold of 2), still half-open
    expect(breaker.getState()).toBe('half-open');
  });

  it('closes again after success threshold in half-open', async () => {
    const breaker = new CircuitBreaker({
      failureThreshold: 2,
      resetTimeout: 100,
      successThreshold: 2,
    });
    const error = new Error('fail');

    // Open the circuit
    for (let i = 0; i < 2; i++) {
      await expect(breaker.execute(async () => { throw error; })).rejects.toThrow();
    }
    expect(breaker.getState()).toBe('open');

    // Wait for reset timeout
    await new Promise((r) => setTimeout(r, 150));

    // Two successful executions should close the circuit
    await breaker.execute(async () => 'ok1');
    expect(breaker.getState()).toBe('half-open');

    await breaker.execute(async () => 'ok2');
    expect(breaker.getState()).toBe('closed');
  });

  it('reset() returns to closed state', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 2, resetTimeout: 60000 });
    const error = new Error('fail');

    // Open the circuit
    for (let i = 0; i < 2; i++) {
      await expect(breaker.execute(async () => { throw error; })).rejects.toThrow();
    }
    expect(breaker.getState()).toBe('open');

    breaker.reset();
    expect(breaker.getState()).toBe('closed');
    expect(breaker.getFailureCount()).toBe(0);
  });

  it('getDiagnostics() returns correct state snapshot', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 5, resetTimeout: 60000 });

    const diag = breaker.getDiagnostics();
    expect(diag).toEqual({
      state: 'closed',
      failureCount: 0,
      successCount: 0,
      lastFailureTime: 0,
      nextAttemptTime: 0,
    });

    // Cause a failure
    await expect(breaker.execute(async () => { throw new Error('fail'); })).rejects.toThrow();

    const diag2 = breaker.getDiagnostics();
    expect(diag2.state).toBe('closed');
    expect(diag2.failureCount).toBe(1);
    expect(diag2.lastFailureTime).toBeGreaterThan(0);
  });

  it('resets failure count on success in closed state', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 5 });

    // Cause some failures
    for (let i = 0; i < 3; i++) {
      await expect(breaker.execute(async () => { throw new Error('fail'); })).rejects.toThrow();
    }
    expect(breaker.getFailureCount()).toBe(3);

    // Success resets failure count
    await breaker.execute(async () => 'ok');
    expect(breaker.getFailureCount()).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// resilientFetch()
// ---------------------------------------------------------------------------

describe('resilientFetch()', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    // Reset global.fetch mock before each test
    global.fetch = jest.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('makes a successful fetch', async () => {
    const mockResponse = new Response(JSON.stringify({ ok: true }), { status: 200 });
    (global.fetch as jest.Mock).mockResolvedValue(mockResponse);

    const response = await resilientFetch('https://example.com/api', undefined, {
      retry: { maxAttempts: 1 },
    });

    expect(response).toBe(mockResponse);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      'https://example.com/api',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('retries on network error', async () => {
    const networkError = new Error('network fetch failed');
    const mockResponse = new Response('ok', { status: 200 });

    (global.fetch as jest.Mock)
      .mockRejectedValueOnce(networkError)
      .mockResolvedValue(mockResponse);

    const response = await resilientFetch('https://example.com/api', undefined, {
      retry: {
        maxAttempts: 2,
        initialDelay: 1,
        retryable: () => true,
      },
    });

    expect(response).toBe(mockResponse);
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('respects circuit breaker state', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 1, resetTimeout: 60000 });

    // Open the circuit breaker by causing a failure
    const networkError = new Error('fail');
    (global.fetch as jest.Mock).mockRejectedValue(networkError);

    await expect(
      resilientFetch('https://example.com/api', undefined, {
        retry: { maxAttempts: 1 },
        circuitBreaker: { breaker },
      })
    ).rejects.toThrow();

    expect(breaker.getState()).toBe('open');

    // Subsequent calls should be rejected by the circuit breaker
    await expect(
      resilientFetch('https://example.com/api', undefined, {
        retry: { maxAttempts: 1 },
        circuitBreaker: { breaker },
      })
    ).rejects.toThrow('Circuit breaker is OPEN');
  });

  it('passes custom RequestInit options through to fetch', async () => {
    const mockResponse = new Response('ok', { status: 200 });
    (global.fetch as jest.Mock).mockResolvedValue(mockResponse);

    await resilientFetch(
      'https://example.com/api',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: 'test' }),
      },
      { retry: { maxAttempts: 1 } }
    );

    expect(global.fetch).toHaveBeenCalledWith(
      'https://example.com/api',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: 'test' }),
      })
    );
  });
});
