import fs from 'fs';
import path from 'path';
import type { NextRequest } from 'next/server';

export const dynamic = 'force-dynamic';

// P1+P2 fix: prefer the rendered dist/ bundle, fall back to source tree.
// `make persona-render` outputs to rooms/persona/dist/ — the source tree
// at rooms/persona/ does NOT contain walkthrough.mp4 or pretext/index.html.
const PERSONA_DIR_CANDIDATES = [
  path.join(process.cwd(), 'data', 'rooms', 'persona', 'dist'),
  path.join(process.cwd(), 'data', 'rooms', 'persona'),
  path.join(process.cwd(), 'rooms', 'persona', 'dist'),
  path.join(process.cwd(), 'rooms', 'persona'),
  path.join(process.cwd(), '..', 'rooms', 'persona', 'dist'),
  path.join(process.cwd(), '..', 'rooms', 'persona'),
];

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
};

function resolvePersonaDir(): string | null {
  for (const p of PERSONA_DIR_CANDIDATES) {
    try {
      if (fs.existsSync(p) && fs.statSync(p).isDirectory()) return p;
    } catch { /* continue */ }
  }
  return null;
}

// P1 fix: catch-all route handles both /persona/livingdoc and /persona/livingdoc/<asset>
// Next.js [...slug] catches all sub-paths, so /persona/livingdoc/walkthrough.mp4
// and /persona/livingdoc/pretext/index.html reach this handler.
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug?: string[] }> }
) {
  const personaDir = resolvePersonaDir();
  if (!personaDir) {
    return new Response('Persona room not found', { status: 404 });
  }

  const { slug } = await params;

  // No slug = root request -> serve index.html
  if (!slug || slug.length === 0) {
    const indexPath = path.join(personaDir, 'index.html');
    try {
      const html = fs.readFileSync(indexPath, 'utf-8');
      return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    } catch {
      return new Response('Persona index.html not found', { status: 404 });
    }
  }

  // Slug present = asset request (walkthrough.mp4, pretext/index.html, etc.)
  const subPath = slug.join('/');
  const requestedFile = path.join(personaDir, subPath);

  // Prevent path traversal
  const resolvedFile = path.resolve(requestedFile);
  const resolvedDir = path.resolve(personaDir);
  if (!resolvedFile.startsWith(resolvedDir + path.sep) && resolvedFile !== resolvedDir) {
    return new Response('Forbidden', { status: 403 });
  }

  try {
    if (!fs.existsSync(resolvedFile) || fs.statSync(resolvedFile).isDirectory()) {
      // Try index.html in subdirectory
      const subIndex = path.join(resolvedFile, 'index.html');
      if (fs.existsSync(subIndex)) {
        const html = fs.readFileSync(subIndex, 'utf-8');
        return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      }
      return new Response('Not found', { status: 404 });
    }

    const ext = path.extname(resolvedFile).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    const data = fs.readFileSync(resolvedFile);

    return new Response(
      new Uint8Array(data),
      {
        headers: {
          'Content-Type': contentType,
          'Cache-Control': 'public, max-age=3600',
        },
      }
    );
  } catch {
    return new Response('File read error', { status: 500 });
  }
}
