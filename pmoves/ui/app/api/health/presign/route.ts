import { NextResponse } from 'next/server';

function resolveBase() {
  const base = process.env.PRESIGN_SERVICE_URL || process.env.PRESIGN_BASE_URL || process.env.NEXT_PUBLIC_PRESIGN_URL || 'http://localhost:8088';
  return base.replace(/\/$/, '');
}

export async function GET() {
  const base = resolveBase();
  const secret = process.env.PRESIGN_SHARED_SECRET || process.env.PRESIGN_SERVICE_TOKEN || '';
  const hasSecret = Boolean(secret);
  const preview = hasSecret ? `Bearer ${secret.length <= 8 ? secret : secret.slice(0,2)}…` : 'none';

  // Probe healthz and an auth-required endpoint
  const health = await fetch(`${base}/healthz`).then(r => r.ok).catch(() => false);
  const noAuth = await fetch(`${base}/presign/get`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ bucket: 'assets', key: 'probe.txt', expires: 60 }) })
    .then(r => r.status).catch(() => 0);
  const withAuth = await fetch(`${base}/presign/get`, { method: 'POST', headers: { 'content-type': 'application/json', ...(hasSecret ? { authorization: `Bearer ${secret}` } : {}) }, body: JSON.stringify({ bucket: 'assets', key: 'probe.txt', expires: 60 }) })
    .then(r => r.status).catch(() => 0);

  return NextResponse.json({ base, hasSecret, authHeaderPreview: preview, healthz: health, statusNoAuth: noAuth, statusWithAuth: withAuth });
}

