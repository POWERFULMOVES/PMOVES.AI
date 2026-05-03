/**
 * A2UI Renderer Service
 *
 * Converts A2UI animation JSON specs into MP4/GIF/WebM via Remotion.
 * Uploads rendered output to MinIO and publishes NATS events.
 *
 * Port: 8105
 * Health: /healthz
 * Metrics: /metrics
 * Auth: JWT (fail-closed) on /render, /render/chart, and /render/provenance
 *
 * Thread 2.1: Remotion Renderer Service
 */

import express, { Request, Response, NextFunction } from 'express';
import { collectDefaultMetrics, register, Counter, Histogram } from 'prom-client';
import { bundle } from '@remotion/bundler';
import { renderMedia, selectComposition } from '@remotion/renderer';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { connect, NatsConnection, StringCodec } from 'nats';
import jwt from 'jsonwebtoken';
import rateLimit from 'express-rate-limit';
import path from 'path';
import fs from 'fs';
import os from 'os';
import crypto from 'crypto';
import {
  estimateProvenanceDurationMs,
  normalizeProvenanceLivingDoc,
  summarizeProvenanceLivingDoc,
} from './provenanceLivingDoc';

const app = express();
const PORT = parseInt(process.env.PORT || '8105', 10);
const sc = StringCodec();

// --- Configuration ---
const SUPABASE_JWT_SECRET = process.env.SUPABASE_JWT_SECRET;
const NATS_URL = process.env.NATS_URL || 'nats://nats:pmoves@nats:4222';
const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT || 'http://minio:9000';
const MINIO_ACCESS_KEY = process.env.MINIO_ACCESS_KEY || 'minioadmin';
const MINIO_SECRET_KEY = process.env.MINIO_SECRET_KEY || 'minioadmin';
const MINIO_BUCKET = process.env.MINIO_BUCKET || 'outputs';

// --- S3 Client (MinIO) ---
const s3 = new S3Client({
  endpoint: MINIO_ENDPOINT,
  region: 'us-east-1',
  credentials: {
    accessKeyId: MINIO_ACCESS_KEY,
    secretAccessKey: MINIO_SECRET_KEY,
  },
  forcePathStyle: true,
});

// --- NATS Connection ---
let nc: NatsConnection | null = null;

async function connectNats(): Promise<void> {
  try {
    nc = await connect({ servers: NATS_URL });
    console.log('NATS connected');
  } catch (err) {
    console.warn('NATS connection failed (non-fatal):', err instanceof Error ? err.message : err);
  }
}

function publishNats(subject: string, data: Record<string, unknown>): void {
  if (!nc) return;
  try {
    nc.publish(subject, sc.encode(JSON.stringify(data)));
  } catch (err) {
    console.warn(`NATS publish to ${subject} failed:`, err instanceof Error ? err.message : err);
  }
}

// --- Remotion Bundle ---
let bundleLocation: string | null = null;

async function ensureBundle(): Promise<string> {
  if (bundleLocation) return bundleLocation;
  const entryCandidates = [
    path.resolve(__dirname, 'remotion', 'index.js'),
    path.resolve(__dirname, 'remotion', 'index.tsx'),
    path.resolve(process.cwd(), 'dist', 'remotion', 'index.js'),
    path.resolve(process.cwd(), 'src', 'remotion', 'index.tsx'),
  ];
  const entryPoint = entryCandidates.find((candidate) => fs.existsSync(candidate));
  if (!entryPoint) {
    throw new Error(`Remotion entry point not found. Checked: ${entryCandidates.join(', ')}`);
  }

  console.log('Bundling Remotion project...');
  bundleLocation = await bundle({ entryPoint });
  console.log('Remotion bundle ready');
  return bundleLocation;
}

// --- Prometheus Metrics ---
collectDefaultMetrics({ prefix: 'a2ui_renderer_' });

const renderCounter = new Counter({
  name: 'a2ui_renders_total',
  help: 'Total render requests',
  labelNames: ['format', 'status'],
});

const renderDuration = new Histogram({
  name: 'a2ui_render_duration_seconds',
  help: 'Render duration in seconds',
  labelNames: ['format'],
  buckets: [0.5, 1, 2, 5, 10, 30, 60, 120],
});

const ALLOWED_RENDER_FORMATS = new Set(['mp4', 'gif', 'webm']);

type LayoutSummary = {
  text_elements: number;
  pretext_elements: number;
  debug_layout_elements: number;
  bounded_text_elements: number;
  engines: string[];
};

/**
 * Summarizes text-layout characteristics used across an A2UI spec's scenes.
 *
 * Iterates all scenes and their elements, counting text/heading elements and collecting layout-related metrics.
 *
 * @param spec - The A2UI specification object to analyze; expected to contain a `scenes` array of scene objects each with an `elements` array.
 * @returns An object describing layout usage:
 *  - `text_elements`: total number of `text` or `heading` elements found
 *  - `pretext_elements`: number of elements using the `pretext` text engine
 *  - `debug_layout_elements`: number of elements with `text_layout.debugBoxes === true`
 *  - `bounded_text_elements`: number of elements that specify a width or maxWidth (via layout, size, or style)
 *  - `engines`: array of unique text layout engine names observed (e.g., `["browser", "pretext"]`)
 */
function summarizeLayoutUsage(spec: any): LayoutSummary {
  const engines = new Set<string>();
  let textElements = 0;
  let pretextElements = 0;
  let debugLayoutElements = 0;
  let boundedTextElements = 0;

  for (const scene of Array.isArray(spec?.scenes) ? spec.scenes : []) {
    for (const element of Array.isArray(scene?.elements) ? scene.elements : []) {
      if (element?.type !== 'text' && element?.type !== 'heading') {
        continue;
      }

      textElements += 1;
      const layout = element?.text_layout;
      const engine = typeof layout?.engine === 'string' ? layout.engine : 'browser';
      engines.add(engine);

      if (engine === 'pretext') {
        pretextElements += 1;
      }
      if (layout?.debugBoxes === true) {
        debugLayoutElements += 1;
      }
      if (
        layout?.maxWidth !== undefined
        || element?.size?.width !== undefined
        || element?.style?.width !== undefined
        || element?.style?.maxWidth !== undefined
      ) {
        boundedTextElements += 1;
      }
    }
  }

  return {
    text_elements: textElements,
    pretext_elements: pretextElements,
    debug_layout_elements: debugLayoutElements,
    bounded_text_elements: boundedTextElements,
    engines: Array.from(engines.values()),
  };
}

/**
 * Normalize and validate a requested render format string.
 *
 * @param rawFormat - The incoming format value (commonly from a query or user input)
 * @returns The canonical lowercase format (`"mp4"`, `"gif"`, or `"webm"`) if allowed, `null` otherwise
 */
function normalizeRenderFormat(rawFormat: unknown): string | null {
  const format = typeof rawFormat === 'string' ? rawFormat.trim().toLowerCase() : 'mp4';
  if (!ALLOWED_RENDER_FORMATS.has(format)) {
    return null;
  }
  return format;
}

const renderLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { ok: false, error: 'Too many render requests, try again later' },
});


type AuthenticatedRequest = Request & { user?: Record<string, unknown> };

// --- JWT Auth Middleware (fail-closed) ---
function requireAuth(req: Request, res: Response, next: NextFunction): void {
  if (!SUPABASE_JWT_SECRET) {
    res.status(500).json({ ok: false, error: 'Server misconfigured: missing JWT secret' });
    return;
  }

  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({ ok: false, error: 'Missing or malformed Authorization header' });
    return;
  }

  const token = authHeader.slice(7);
  try {
    const decoded = jwt.verify(token, SUPABASE_JWT_SECRET) as Record<string, unknown>;
    if (decoded.role === 'anon') {
      res.status(403).json({ ok: false, error: 'Anonymous access denied' });
      return;
    }

    // Attach decoded token to request
    (req as AuthenticatedRequest).user = decoded;

    // CHIT Safe Passage attestation header
    const attestation = Buffer.from(JSON.stringify({
      version: 'chit.cgp.v1.0',
      transit: 'a2ui-renderer',
      timestamp: new Date().toISOString(),
    })).toString('base64');
    res.setHeader('X-CHIT-Attestation', attestation);

    next();
  } catch {
    res.status(401).json({ ok: false, error: 'Invalid or expired token' });
  }
}

// --- MinIO Upload ---
async function uploadToMinIO(filePath: string, key: string, contentType: string): Promise<string> {
  const fileBuffer = fs.readFileSync(filePath);
  await s3.send(new PutObjectCommand({
    Bucket: MINIO_BUCKET,
    Key: key,
    Body: fileBuffer,
    ContentType: contentType,
  }));
  return `${MINIO_ENDPOINT}/${MINIO_BUCKET}/${key}`;
}

/**
 * Infer the ingest kind for a media file based on its format.
 *
 * @param format - The render or file format (for example: `'mp4'`, `'gif'`, `'webm'`)
 * @returns `image` for `'gif'`, `video` for `'mp4'` or `'webm'`, `other` for any other format
 */
function inferIngestKind(format: string): 'audio' | 'video' | 'image' | 'document' | 'other' {
  if (format === 'gif') return 'image';
  if (format === 'mp4' || format === 'webm') return 'video';
  return 'other';
}

/**
 * Map a render format identifier to the appropriate HTTP MIME type.
 *
 * @param format - Format string such as 'mp4', 'webm', or 'gif'
 * @returns The MIME type for the given format: `'image/gif'` for `gif`, `'video/webm'` for `webm`, otherwise `'video/mp4'`
 */
function inferContentType(format: string): string {
  if (format === 'gif') return 'image/gif';
  if (format === 'webm') return 'video/webm';
  return 'video/mp4';
}

// --- Middleware ---
app.use(express.json({ limit: '10mb' }));

// --- Public Endpoints ---

app.get('/healthz', (_req, res) => {
  res.json({
    status: 'healthy',
    service: 'a2ui-renderer',
    version: '2.0.0',
    port: PORT,
    remotion: true,
    nats: nc !== null,
  });
});

app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', register.contentType);
  res.send(await register.metrics());
});

// --- Protected Endpoints ---

/**
 * POST /render
 *
 * Accepts an A2UI animation spec and renders it to the requested format.
 * Uploads result to MinIO and publishes NATS events.
 *
 * Body: A2UI animation JSON (see a2ui-animation-schema.json)
 * Query: ?format=mp4|gif|webm (default: mp4)
 *
 * Returns: { ok: true, url: "...", duration_ms: ... }
 */
app.post('/render', renderLimiter, requireAuth, async (req: Request, res: Response) => {
  const format = normalizeRenderFormat(req.query.format);
  if (!format) {
    res.status(400).json({
      ok: false,
      error: `Unsupported format: must be one of ${Array.from(ALLOWED_RENDER_FORMATS).join(', ')}`,
    });
    return;
  }
  const spec = req.body;
  const end = renderDuration.startTimer({ format });
  const layoutSummary = summarizeLayoutUsage(spec);

  let tmpDir: string | undefined;
  try {
    if (!spec.version || !spec.animation || !spec.scenes) {
      renderCounter.inc({ format, status: 'error' });
      res.status(400).json({
        ok: false,
        error: 'Invalid A2UI spec: missing version, animation, or scenes',
      });
      return;
    }

    const servedUrl = await ensureBundle();
    const compositionId = spec.metadata?.compositionId || 'A2UIComposition';
    const durationInFrames = Math.ceil(((spec.animation.duration_ms || 6000) / 1000) * 30);

    const composition = await selectComposition({
      serveUrl: servedUrl,
      id: compositionId,
      inputProps: { spec },
    });

    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'a2ui-'));
    const outputFile = path.join(tmpDir, `render.${format}`);

    const codec = format === 'gif' ? 'gif' as const : format === 'webm' ? 'vp8' as const : 'h264' as const;

    await renderMedia({
      composition: { ...composition, durationInFrames },
      serveUrl: servedUrl,
      codec,
      outputLocation: outputFile,
      inputProps: { spec },
    });

    // Upload to MinIO
    const renderKey = `a2ui/${Date.now()}-${crypto.randomBytes(4).toString('hex')}.${format}`;
    const contentType = format === 'gif' ? 'image/gif' : format === 'webm' ? 'video/webm' : 'video/mp4';
    const url = await uploadToMinIO(outputFile, renderKey, contentType);

    // Publish NATS events
    publishNats('ingest.file.added.v1', {
      file_id: renderKey,
      uri: `s3://${MINIO_BUCKET}/${renderKey}`,
      kind: inferIngestKind(format),
      meta: {
        bucket: MINIO_BUCKET,
        format,
        source: 'a2ui-renderer',
        agent_id: process.env.PROVENANCE_AGENT_ID || 'unknown',
        timestamp: new Date().toISOString(),
      },
    });

    publishNats('a2ui.render.completed.v1', {
      render_key: renderKey,
      format,
      duration_ms: spec.animation.duration_ms || 6000,
      scenes: spec.scenes.length,
      composition_id: compositionId,
      layout_summary: layoutSummary,
      timestamp: new Date().toISOString(),
    });

    // Graphiti emission (fire-and-forget)
    publishNats('agent.graphiti.signed.v1', {
      agent_id: process.env.PROVENANCE_AGENT_ID || 'unknown',
      glyph: '\u2726',
      color: '#E11D48',
      phase: 'a2ui-render',
      timestamp: new Date().toISOString(),
      summary: `Rendered ${format} from A2UI spec (${spec.scenes.length} scenes)`,
    });

    // Cleanup
    fs.rmSync(tmpDir, { recursive: true, force: true });

    renderCounter.inc({ format, status: 'success' });
    end();

    res.json({
      ok: true,
      url,
      format,
      duration_ms: spec.animation.duration_ms || 6000,
      scenes: spec.scenes.length,
      spec_version: spec.version,
      layout_summary: layoutSummary,
    });
  } catch (err) {
    if (tmpDir) {
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
    renderCounter.inc({ format, status: 'error' });
    end();
    res.status(500).json({
      ok: false,
      error: err instanceof Error ? err.message : 'Unknown render error',
    });
  }
});

/**
 * POST /render/chart
 *
 * Shorthand for rendering benchmark chart data directly.
 * Wraps the data in an A2UI spec automatically.
 */
app.post('/render/chart', renderLimiter, requireAuth, async (req: Request, res: Response) => {
  const { title, labels, values, type = 'bar_chart' } = req.body;

  const spec = {
    version: 'a2ui.animation.v1',
    metadata: { title: title || 'Chart', compositionId: 'A2UIComposition' },
    animation: {
      engine: 'remotion',
      duration_ms: 6000,
      bpm: 10,
    },
    scenes: [
      {
        id: 'chart',
        label: title || 'Chart',
        duration_ms: 6000,
        elements: [
          {
            type,
            content: { labels, values },
            enter_at_ms: 0,
          },
        ],
      },
    ],
  };
  const layoutSummary = summarizeLayoutUsage(spec);

  // Delegate to render logic inline
  req.body = spec;
  req.query.format = 'mp4';

  const end = renderDuration.startTimer({ format: 'mp4' });
  let tmpDir: string | undefined;

  try {
    const servedUrl = await ensureBundle();
    const durationInFrames = 180; // 6s at 30fps

    const composition = await selectComposition({
      serveUrl: servedUrl,
      id: 'A2UIComposition',
      inputProps: { spec },
    });

    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'a2ui-chart-'));
    const outputFile = path.join(tmpDir, 'chart.mp4');

    await renderMedia({
      composition: { ...composition, durationInFrames },
      serveUrl: servedUrl,
      codec: 'h264',
      outputLocation: outputFile,
      inputProps: { spec },
    });

    const renderKey = `a2ui/charts/${Date.now()}-${crypto.randomBytes(4).toString('hex')}.mp4`;
    const url = await uploadToMinIO(outputFile, renderKey, 'video/mp4');

    publishNats('ingest.file.added.v1', {
      file_id: renderKey,
      uri: `s3://${MINIO_BUCKET}/${renderKey}`,
      kind: 'video',
      meta: {
        bucket: MINIO_BUCKET,
        format: 'mp4',
        source: 'a2ui-renderer',
        agent_id: process.env.PROVENANCE_AGENT_ID || 'unknown',
        timestamp: new Date().toISOString(),
      },
    });

    publishNats('a2ui.render.completed.v1', {
      render_key: renderKey,
      format: 'mp4',
      duration_ms: 6000,
      scenes: 1,
      composition_id: 'A2UIComposition',
      layout_summary: layoutSummary,
      timestamp: new Date().toISOString(),
    });

    fs.rmSync(tmpDir, { recursive: true, force: true });

    renderCounter.inc({ format: 'mp4', status: 'success' });
    end();

    res.json({ ok: true, url, format: 'mp4', duration_ms: 6000, scenes: 1, layout_summary: layoutSummary });
  } catch (err) {
    if (tmpDir) {
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
    renderCounter.inc({ format: 'mp4', status: 'error' });
    end();
    res.status(500).json({
      ok: false,
      error: err instanceof Error ? err.message : 'Unknown chart render error',
    });
  }
});

/**
 * POST /render/provenance
 *
 * Render a provenance-shaped living document directly into a Remotion composition.
 * This is the preferred surface for transcript overlays, semantic-weight review,
 * and motion-ready living docs that share the same source bundle as HiRAG.
 */
app.post('/render/provenance', renderLimiter, requireAuth, async (req: Request, res: Response) => {
  const format = normalizeRenderFormat(req.query.format);
  if (!format) {
    res.status(400).json({
      ok: false,
      error: `Unsupported format: must be one of ${Array.from(ALLOWED_RENDER_FORMATS).join(', ')}`,
    });
    return;
  }

  const doc = normalizeProvenanceLivingDoc({
    ...req.body,
    duration_ms: req.body?.duration_ms ?? estimateProvenanceDurationMs(req.body ?? {}),
  });
  const docSummary = summarizeProvenanceLivingDoc(doc);
  const end = renderDuration.startTimer({ format });

  let tmpDir: string | undefined;
  try {
    const servedUrl = await ensureBundle();
    const durationInFrames = Math.ceil((doc.duration_ms / 1000) * 30);

    const composition = await selectComposition({
      serveUrl: servedUrl,
      id: 'ProvenanceLivingDoc',
      inputProps: { doc },
    });

    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'a2ui-provenance-'));
    const outputFile = path.join(tmpDir, `provenance.${format}`);
    const codec = format === 'gif' ? 'gif' as const : format === 'webm' ? 'vp8' as const : 'h264' as const;

    await renderMedia({
      composition: { ...composition, durationInFrames },
      serveUrl: servedUrl,
      codec,
      outputLocation: outputFile,
      inputProps: { doc },
    });

    const renderKey = `a2ui/provenance/${Date.now()}-${crypto.randomBytes(4).toString('hex')}.${format}`;
    const url = await uploadToMinIO(outputFile, renderKey, inferContentType(format));

    publishNats('ingest.file.added.v1', {
      file_id: renderKey,
      uri: `s3://${MINIO_BUCKET}/${renderKey}`,
      kind: inferIngestKind(format),
      meta: {
        bucket: MINIO_BUCKET,
        format,
        source: 'a2ui-renderer',
        artifact_kind: 'provenance-living-doc',
        agent_id: process.env.PROVENANCE_AGENT_ID || 'unknown',
        timestamp: new Date().toISOString(),
      },
    });

    publishNats('a2ui.render.completed.v1', {
      render_key: renderKey,
      format,
      duration_ms: doc.duration_ms,
      scenes: doc.sections.length,
      composition_id: 'ProvenanceLivingDoc',
      provenance_summary: docSummary,
      timestamp: new Date().toISOString(),
    });

    publishNats('agent.graphiti.signed.v1', {
      agent_id: process.env.PROVENANCE_AGENT_ID || 'unknown',
      glyph: '\u2726',
      color: '#E11D48',
      phase: 'a2ui-provenance',
      timestamp: new Date().toISOString(),
      summary: `Rendered ${format} provenance living doc (${doc.sections.length} sections)`,
    });

    fs.rmSync(tmpDir, { recursive: true, force: true });

    renderCounter.inc({ format, status: 'success' });
    end();

    res.json({
      ok: true,
      url,
      format,
      duration_ms: doc.duration_ms,
      composition_id: 'ProvenanceLivingDoc',
      provenance_summary: docSummary,
      title: doc.title,
      merkle_root: doc.merkle_root,
      shape_id: doc.shape_id,
    });
  } catch (err) {
    if (tmpDir) {
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
    renderCounter.inc({ format, status: 'error' });
    end();
    res.status(500).json({
      ok: false,
      error: err instanceof Error ? err.message : 'Unknown provenance render error',
    });
  }
});

// --- Startup ---
app.listen(PORT, '0.0.0.0', async () => {
  console.log(`A2UI Renderer listening on http://0.0.0.0:${PORT}`);
  console.log(`Health: http://127.0.0.1:${PORT}/healthz`);
  console.log(`Metrics: http://127.0.0.1:${PORT}/metrics`);

  await connectNats();

  // Pre-bundle Remotion project (non-blocking)
  ensureBundle().catch((err) => {
    console.warn('Remotion pre-bundle failed (will retry on first render):', err.message);
    bundleLocation = null;
  });
});
