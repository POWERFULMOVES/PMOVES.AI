import { NextResponse } from 'next/server';

/**
 * Simple in-memory rate limiter to prevent quota exhaustion.
 * Tracks request counts per IP address.
 */
class RateLimiter {
  private requests: Map<string, { count: number; resetTime: number }> = new Map();
  private readonly maxRequests: number;
  private readonly windowMs: number;

  constructor(maxRequests: number = 10, windowMs: number = 60000) {
    this.maxRequests = maxRequests;
    this.windowMs = windowMs;
  }

  /**
   * Checks if a request should be allowed.
   * @param identifier - IP address or other identifier
   * @returns true if request is allowed, false if rate limited
   */
  check(identifier: string): boolean {
    const now = Date.now();
    const record = this.requests.get(identifier);

    if (!record || now > record.resetTime) {
      // First request or window expired
      this.requests.set(identifier, {
        count: 1,
        resetTime: now + this.windowMs,
      });
      return true;
    }

    if (record.count >= this.maxRequests) {
      return false;
    }

    record.count++;
    return true;
  }

  /**
   * Gets remaining request count for an identifier.
   */
  getRemaining(identifier: string): number {
    const record = this.requests.get(identifier);
    if (!record || Date.now() > record.resetTime) {
      return this.maxRequests;
    }
    return Math.max(0, this.maxRequests - record.count);
  }

  /**
   * Cleans up expired entries to prevent memory leaks.
   */
  cleanup(): void {
    const now = Date.now();
    for (const [key, record] of this.requests.entries()) {
      if (now > record.resetTime) {
        this.requests.delete(key);
      }
    }
  }
}

// Global rate limiter instance (10 requests per minute per IP)
const rateLimiter = new RateLimiter(10, 60000);

// Cleanup expired entries every 5 minutes
if (typeof setInterval !== 'undefined') {
  setInterval(() => rateLimiter.cleanup(), 300000);
}

function resolveBase() {
  const base = process.env.PRESIGN_SERVICE_URL || process.env.PRESIGN_BASE_URL || process.env.NEXT_PUBLIC_PRESIGN_URL || 'http://localhost:8088';
  return base.replace(/\/$/, '');
}

/**
 * Extracts client IP from request headers.
 * Handles various proxy configurations (X-Forwarded-For, CF-Connecting-IP, etc.)
 */
function getClientIp(request: Request): string {
  // Try various headers in order of preference
  const headers = request.headers;
  return (
    headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
    headers.get('cf-connecting-ip') ||
    headers.get('x-real-ip') ||
    'unknown'
  );
}

export async function GET(request: Request) {
  // Rate limiting to prevent quota exhaustion
  const clientIp = getClientIp(request);
  if (!rateLimiter.check(clientIp)) {
    const remaining = rateLimiter.getRemaining(clientIp);
    return NextResponse.json(
      {
        error: 'Too many requests',
        message: `Rate limit exceeded. Please try again later.`,
        retryAfter: 60,
      },
      {
        status: 429,
        headers: {
          'Retry-After': '60',
          'X-RateLimit-Remaining': remaining.toString(),
          'X-RateLimit-Limit': rateLimiter['maxRequests'].toString(),
        },
      }
    );
  }

  const base = resolveBase();
  const hasSecret = Boolean(
    process.env.PRESIGN_SHARED_SECRET || process.env.PRESIGN_SERVICE_TOKEN
  );

  // Probe healthz endpoint only (no presign endpoint calls to avoid quota exhaustion)
  let healthz = false;
  let healthzError: string | undefined;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(`${base}/healthz`, {
      signal: controller.signal,
    });
    healthz = response.ok;
    clearTimeout(timeoutId);
  } catch (err) {
    healthz = false;
    healthzError = err instanceof Error ? err.message : 'Unknown error';
  }

  // Return rate limit headers with remaining quota
  const remaining = rateLimiter.getRemaining(clientIp);

  return NextResponse.json(
    {
      service: 'presign-health',
      base,
      hasSecret,
      healthz,
      healthzError,
      timestamp: new Date().toISOString(),
    },
    {
      headers: {
        'X-RateLimit-Remaining': remaining.toString(),
        'X-RateLimit-Limit': rateLimiter['maxRequests'].toString(),
      },
    }
  );
}

