import { type NextRequest } from 'next/server';
import { getBootJwt } from './supabaseClient';
import { logError } from './errorUtils';
import { ErrorIds } from './constants/errorIds';

export interface OwnerResult {
  ownerId: string | null;
  error?: string;
}

/**
 * Decode a JWT payload and extract the `sub` claim.
 * Handles base64url encoding (RFC 4648).
 */
function decodeJwtSub(token: string): string | null {
  const parts = token.split('.');
  if (parts.length !== 3) return null;

  let payload = parts[1];
  payload = payload.replace(/-/g, '+').replace(/_/g, '/');
  const padding = payload.length % 4;
  if (padding) payload += '='.repeat(4 - padding);

  const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
  return typeof json.sub === 'string' ? json.sub : null;
}

/**
 * Authenticate an incoming API request by extracting identity from the JWT.
 *
 * Resolution order:
 * 1. Authorization header (Bearer token) from the request
 * 2. Boot JWT from environment (single-user/operator mode fallback)
 *
 * @param request - The incoming NextRequest
 * @param component - Component name for structured error logging
 */
export function authenticateRequest(request: NextRequest, component: string): OwnerResult {
  try {
    // 1. Try request Authorization header first (per-request identity)
    const authHeader = request.headers.get('authorization');
    if (authHeader?.startsWith('Bearer ')) {
      const token = authHeader.slice(7);
      const sub = decodeJwtSub(token);
      if (sub) return { ownerId: sub };
    }

    // 2. Fall back to boot JWT (single-user operator mode)
    const bootToken = getBootJwt();
    if (!bootToken) {
      logError('No JWT: no Authorization header and no boot JWT configured', new Error('Missing authentication'), 'warning', {
        errorId: ErrorIds.JWT_MISSING_HEADER,
        component,
      });
      return { ownerId: null, error: 'Authentication required' };
    }

    const sub = decodeJwtSub(bootToken);
    if (!sub) {
      logError('Boot JWT has no sub claim', new Error('Invalid boot JWT'), 'warning', {
        errorId: ErrorIds.JWT_INVALID_FORMAT,
        component,
      });
      return { ownerId: null, error: 'Invalid JWT token' };
    }

    return { ownerId: sub };
  } catch (e) {
    logError('JWT authentication failed', e, 'error', {
      errorId: ErrorIds.JWT_PARSE_FAILED,
      component,
    });
    return { ownerId: null, error: 'Authentication failed' };
  }
}

/**
 * Extract owner ID from boot JWT token (legacy single-user mode).
 * Properly handles base64url encoding (RFC 4648).
 *
 * @deprecated Prefer authenticateRequest() for API routes — it supports per-request identity.
 * @param component - Optional component name for error logging context
 * @returns Object with ownerId (user ID from JWT sub claim) and error
 */
export function ownerFromJwt(component?: string): OwnerResult {
  try {
    const token = getBootJwt();
    if (!token) {
      return { ownerId: null, error: 'No JWT token available' };
    }

    const sub = decodeJwtSub(token);
    if (!sub) {
      logError('Invalid JWT format', new Error('JWT decode failed'), 'warning', {
        errorId: ErrorIds.JWT_INVALID_FORMAT,
        component: component || 'jwtUtils',
      });
      return { ownerId: null, error: 'Invalid JWT format' };
    }

    return { ownerId: sub };
  } catch (e) {
    logError('JWT parsing failed', e, 'error', {
      errorId: ErrorIds.JWT_PARSE_FAILED,
      component: component || 'jwtUtils'
    });
    return { ownerId: null, error: 'Failed to parse JWT' };
  }
}
