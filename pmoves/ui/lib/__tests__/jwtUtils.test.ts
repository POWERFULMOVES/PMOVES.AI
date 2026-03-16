/**
 * Unit tests for lib/jwtUtils.ts
 *
 * Tests authenticateRequest() and ownerFromJwt() — security-critical functions
 * that extract user identity from JWTs.
 */

import { authenticateRequest, ownerFromJwt } from '../jwtUtils';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock getBootJwt from supabaseClient
let mockBootJwt: string | undefined;
jest.mock('../supabaseClient', () => ({
  getBootJwt: () => mockBootJwt,
}));

// Mock logError to prevent console noise in tests
jest.mock('../errorUtils', () => ({
  logError: jest.fn(),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal JWT (header.payload.signature) for testing. */
function makeJwt(payload: Record<string, unknown>): string {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return `${header}.${body}.fake-signature`;
}

/** Create a minimal NextRequest-like object with optional headers. */
function makeRequest(headers: Record<string, string> = {}) {
  const headerMap = new Map(Object.entries(headers));
  return {
    headers: {
      get: (key: string) => headerMap.get(key.toLowerCase()) ?? null,
    },
  } as any; // cast to NextRequest for testing purposes
}

// ---------------------------------------------------------------------------
// ownerFromJwt()
// ---------------------------------------------------------------------------

describe('ownerFromJwt()', () => {
  beforeEach(() => {
    mockBootJwt = undefined;
  });

  it('returns ownerId when valid boot JWT is available', () => {
    mockBootJwt = makeJwt({ sub: 'user-123', exp: 9999999999 });
    const result = ownerFromJwt();
    expect(result.ownerId).toBe('user-123');
    expect(result.error).toBeUndefined();
  });

  it('returns null ownerId when no JWT is available', () => {
    mockBootJwt = undefined;
    const result = ownerFromJwt();
    expect(result.ownerId).toBeNull();
    expect(result.error).toBeDefined();
  });

  it('returns null ownerId for invalid JWT format (not 3 parts)', () => {
    mockBootJwt = 'only-two.parts';
    const result = ownerFromJwt();
    expect(result.ownerId).toBeNull();
    expect(result.error).toBeDefined();
  });

  it('handles base64url encoding correctly (- and _ characters)', () => {
    // Manually craft a payload with base64url characters
    const payload = { sub: 'user-with-special-id+/=test' };
    const payloadB64url = Buffer.from(JSON.stringify(payload)).toString('base64url');
    // Verify the base64url encoding contains - or _ (it may not always, but the
    // decoder must handle them regardless)
    const header = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64url');
    mockBootJwt = `${header}.${payloadB64url}.sig`;
    const result = ownerFromJwt();
    expect(result.ownerId).toBe('user-with-special-id+/=test');
  });

  it('returns null ownerId when JWT has no sub claim', () => {
    mockBootJwt = makeJwt({ name: 'Alice', exp: 9999999999 });
    const result = ownerFromJwt();
    expect(result.ownerId).toBeNull();
    expect(result.error).toBeDefined();
  });

  it('returns null ownerId when JWT payload is not valid JSON', () => {
    mockBootJwt = 'header.!!!not-base64.signature';
    const result = ownerFromJwt();
    expect(result.ownerId).toBeNull();
  });

  it('passes component name through for error logging context', () => {
    mockBootJwt = undefined;
    const result = ownerFromJwt('my-component');
    expect(result.ownerId).toBeNull();
    // The error message should be present; component is used internally for logging
    expect(result.error).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// authenticateRequest()
// ---------------------------------------------------------------------------

describe('authenticateRequest()', () => {
  beforeEach(() => {
    mockBootJwt = undefined;
  });

  it('extracts ownerId from Authorization Bearer header', () => {
    const token = makeJwt({ sub: 'req-user-456' });
    const request = makeRequest({ authorization: `Bearer ${token}` });
    const result = authenticateRequest(request, 'test');
    expect(result.ownerId).toBe('req-user-456');
    expect(result.error).toBeUndefined();
  });

  it('falls back to boot JWT when no Authorization header', () => {
    mockBootJwt = makeJwt({ sub: 'boot-user-789' });
    const request = makeRequest(); // no auth header
    const result = authenticateRequest(request, 'test');
    expect(result.ownerId).toBe('boot-user-789');
    expect(result.error).toBeUndefined();
  });

  it('returns error when neither header nor boot JWT available', () => {
    mockBootJwt = undefined;
    const request = makeRequest(); // no auth header
    const result = authenticateRequest(request, 'test');
    expect(result.ownerId).toBeNull();
    expect(result.error).toBe('Authentication required');
  });

  it('handles malformed Bearer tokens gracefully (no sub)', () => {
    const token = makeJwt({ name: 'no-sub' }); // valid JWT but missing sub
    const request = makeRequest({ authorization: `Bearer ${token}` });
    // With no sub in the bearer token, it should fall through to boot JWT
    mockBootJwt = undefined;
    const result = authenticateRequest(request, 'test');
    expect(result.ownerId).toBeNull();
    expect(result.error).toBe('Authentication required');
  });

  it('falls through non-Bearer auth headers to boot JWT', () => {
    mockBootJwt = makeJwt({ sub: 'boot-fallback' });
    const request = makeRequest({ authorization: 'Basic dXNlcjpwYXNz' });
    const result = authenticateRequest(request, 'test');
    // Non-Bearer header should be ignored, fall back to boot JWT
    expect(result.ownerId).toBe('boot-fallback');
  });

  it('prefers Authorization header over boot JWT', () => {
    mockBootJwt = makeJwt({ sub: 'boot-user' });
    const headerToken = makeJwt({ sub: 'header-user' });
    const request = makeRequest({ authorization: `Bearer ${headerToken}` });
    const result = authenticateRequest(request, 'test');
    expect(result.ownerId).toBe('header-user');
  });

  it('returns error when boot JWT has no sub claim', () => {
    mockBootJwt = makeJwt({ name: 'no-sub-boot' });
    const request = makeRequest(); // no auth header
    const result = authenticateRequest(request, 'test');
    expect(result.ownerId).toBeNull();
    expect(result.error).toBe('Invalid JWT token');
  });

  it('handles completely invalid bearer token gracefully', () => {
    const request = makeRequest({ authorization: 'Bearer not.a.valid.jwt.token' });
    mockBootJwt = undefined;
    const result = authenticateRequest(request, 'test');
    // 4 dots = 5 parts, decodeJwtSub checks for exactly 3 parts
    expect(result.ownerId).toBeNull();
  });
});
