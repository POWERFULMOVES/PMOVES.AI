import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const PERSONA_DIR_CANDIDATES = [
  path.join(process.cwd(), 'data', 'rooms', 'persona'),
  path.join(process.cwd(), 'rooms', 'persona'),
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

export async function GET(request: Request) {
  const personaDir = resolvePersonaDir();
  if (!personaDir) {
    return new Response('Persona room not found', { status: 404 });
  }

  const url = new URL(request.url);
  const pathname = url.pathname;

  if (pathname === '/persona/livingdoc' || pathname === '/persona/livingdoc/') {
    const indexPath = path.join(personaDir, 'index.html');
    try {
      const html = fs.readFileSync(indexPath, 'utf-8');
      return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    } catch {
      return new Response('Persona index.html not found', { status: 404 });
    }
  }

  // Serve static assets from the persona directory (pretext/, walkthrough.mp4, etc.)
  const subPath = pathname.replace(/^\/persona\/livingdoc\//, '');
  const requestedFile = path.join(personaDir, subPath);

  // Prevent path traversal
  if (!requestedFile.startsWith(personaDir)) {
    return new Response('Forbidden', { status: 403 });
  }

  try {
    if (!fs.existsSync(requestedFile) || fs.statSync(requestedFile).isDirectory()) {
      // Try index.html in subdirectory
      const subIndex = path.join(requestedFile, 'index.html');
      if (fs.existsSync(subIndex)) {
        const html = fs.readFileSync(subIndex, 'utf-8');
        return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      }
      return new Response('Not found', { status: 404 });
    }

    const ext = path.extname(requestedFile).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    const isBinary = !['.html', '.css', '.js', '.json', '.svg'].includes(ext);
    const data = fs.readFileSync(requestedFile);

    return new Response(
      isBinary ? data : new Uint8Array(data),
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
