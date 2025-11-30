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

function resolveServiceBase(): string {
  const base =
    process.env.PRESIGN_SERVICE_URL ||
    process.env.PRESIGN_BASE_URL ||
    process.env.NEXT_PUBLIC_PRESIGN_URL ||
    'http://localhost:8088';
  return base.replace(/\/$/, '');
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
  const base = resolveServiceBase();
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

  const doFetch = (authHeaders: Record<string, string>) => fetch(endpoint, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify(payload),
  });

  // Try once with configured secret; if unauthorized and a common default is expected, retry with 'change_me'
  let response = await doFetch(headers);
  if ((response.status === 401 || response.status === 403) && (!sharedSecret || sharedSecret !== 'change_me')) {
    const retryHeaders = { ...headers, authorization: 'Bearer change_me' };
    response = await doFetch(retryHeaders);
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Presign service request failed (${response.status})`);
  }

  return response.json();
}
