/**
 * PMOVES Presign Service Client
 *
 * Generates short-lived, presigned URLs for secure S3/MinIO access.
 *
 * Service URL resolution via PMOVES service discovery:
 * 1. PRESIGN_SHARED_SECRET / NEXT_PUBLIC_PRESIGN_URL environment variables
 * 2. Service catalog (Supabase) via service registry
 * 3. Docker DNS fallback (presign:8088)
 */

import { getServiceUrl } from './serviceDiscovery';

export type PresignMethod = 'put' | 'get' | 'post';

export type PresignOptions = {
  bucket: string;
  key: string;
  contentType?: string;
  expires?: number;
  method?: PresignMethod;
};

export type PresignResult = {
  url: string;
  method: string;
  headers?: Record<string, string>;
  fields?: Record<string, string>;
};

/**
 * Resolves Presign service URL using PMOVES service discovery.
 *
 * Resolution priority:
 * 1. NEXT_PUBLIC_PRESIGN_URL environment variable (explicit override)
 * 2. Service catalog (Supabase) via service registry
 * 3. Docker DNS fallback (presign:8088)
 */
async function resolveServiceBase(): Promise<string> {
  // Check environment variable first
  const envUrl =
    process.env.PRESIGN_SERVICE_URL ||
    process.env.PRESIGN_BASE_URL ||
    process.env.NEXT_PUBLIC_PRESIGN_URL;

  if (envUrl) {
    return envUrl.replace(/\/$/, '');
  }

  // Use service discovery
  return getServiceUrl({
    slug: 'presign',
    defaultPort: 8088,
    envVar: 'NEXT_PUBLIC_PRESIGN_URL',
  });
}

function buildEndpoint(method: PresignMethod): string {
  switch (method) {
    case 'get':
      return '/presign/get';
    case 'post':
      return '/presign/post';
    case 'put':
    default:
      return '/presign/put';
  }
}

export async function callPresignService(options: PresignOptions): Promise<PresignResult> {
  const { bucket, key, contentType, expires, method = 'put' } = options;
  const base = await resolveServiceBase();
  const endpoint = `${base}${buildEndpoint(method)}`;
  const headers: Record<string, string> = {
    'content-type': 'application/json',
  };
  const sharedSecret = process.env.PRESIGN_SHARED_SECRET || process.env.PRESIGN_SERVICE_TOKEN;
  if (sharedSecret) {
    headers.authorization = `Bearer ${sharedSecret}`;
  }

  const payload: Record<string, unknown> = {
    bucket,
    key,
  };
  if (typeof expires === 'number') {
    payload.expires = expires;
  }
  if (contentType) {
    payload.content_type = contentType;
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    // Provide actionable error for auth failures
    if (response.status === 401 || response.status === 403) {
      throw new Error(
        `Presign service authentication failed (${response.status}). ` +
        'Ensure PRESIGN_SHARED_SECRET is configured correctly.'
      );
    }
    throw new Error(text || `Presign service request failed (${response.status})`);
  }

  return response.json();
}
