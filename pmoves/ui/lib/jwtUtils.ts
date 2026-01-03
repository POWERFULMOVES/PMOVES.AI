import { getBootJwt } from './supabaseClient';
import { logError } from './errorUtils';
import { ErrorIds } from './constants/errorIds';

export interface OwnerResult {
  ownerId: string | null;
  error?: string;
}

/**
 * Extract owner ID from JWT token.
 * Properly handles base64url encoding (RFC 4648).
 *
 * @param component - Optional component name for error logging context
 * @returns Object with ownerId (user ID from JWT sub claim) and error
 */
export function ownerFromJwt(component?: string): OwnerResult {
  try {
    const token = getBootJwt();
    if (!token) {
      return { ownerId: null, error: 'No JWT token available' };
    }

    const parts = token.split('.');
    if (parts.length !== 3) {
      logError('Invalid JWT format (must have 3 parts)', new Error('JWT must have 3 parts'), 'warning', {
        errorId: ErrorIds.JWT_INVALID_FORMAT,
        component: component || 'jwtUtils',
      });
      return { ownerId: null, error: 'Invalid JWT format' };
    }

    // Base64url to Base64 conversion (RFC 4648)
    let payload = parts[1];
    payload = payload.replace(/-/g, '+').replace(/_/g, '/');

    // Add padding if needed
    const padding = payload.length % 4;
    if (padding) {
      payload += '='.repeat(4 - padding);
    }

    const json = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as { sub?: string };
    return {
      ownerId: typeof json.sub === 'string' ? json.sub : null,
    };
  } catch (e) {
    logError('JWT parsing failed', e, 'error', {
      errorId: ErrorIds.JWT_PARSE_FAILED,
      component: component || 'jwtUtils'
    });
    return { ownerId: null, error: 'Failed to parse JWT' };
  }
}
