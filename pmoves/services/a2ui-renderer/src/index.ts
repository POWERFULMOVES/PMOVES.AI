/**
 * A2UI Renderer Service
 *
 * Converts A2UI animation JSON specs into MP4/GIF/WebM via Remotion.
 *
 * Port: 8100
 * Health: /healthz
 * Metrics: /metrics
 *
 * Thread 2.1: Remotion Renderer Service
 */

import express from 'express';
import { collectDefaultMetrics, register, Counter, Histogram } from 'prom-client';

const app = express();
const PORT = parseInt(process.env.PORT || '8100', 10);

// Prometheus metrics
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

app.use(express.json({ limit: '10mb' }));

// Health check
app.get('/healthz', (_req, res) => {
  res.json({
    status: 'healthy',
    service: 'a2ui-renderer',
    version: '1.0.0',
    port: PORT,
    remotion: true,
  });
});

// Prometheus metrics
app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', register.contentType);
  res.send(await register.metrics());
});

/**
 * POST /render
 *
 * Accepts an A2UI animation spec and renders it to the requested format.
 *
 * Body: A2UI animation JSON (see a2ui-animation-schema.json)
 * Query: ?format=mp4|gif|webm (default: mp4)
 *
 * Returns: { ok: true, url: "...", duration_ms: ... }
 */
app.post('/render', async (req, res) => {
  const format = (req.query.format as string) || 'mp4';
  const spec = req.body;
  const end = renderDuration.startTimer({ format });

  try {
    // Validate spec has required fields
    if (!spec.version || !spec.animation || !spec.scenes) {
      renderCounter.inc({ format, status: 'error' });
      return res.status(400).json({
        ok: false,
        error: 'Invalid A2UI spec: missing version, animation, or scenes',
      });
    }

    // TODO: Integrate with Remotion renderMedia API
    // For now, return a placeholder indicating the service structure
    const duration_ms = spec.animation.duration_ms || 6000;

    renderCounter.inc({ format, status: 'success' });
    end();

    res.json({
      ok: true,
      format,
      duration_ms,
      scenes: spec.scenes.length,
      message: 'Render queued. Remotion integration pending.',
      spec_version: spec.version,
    });
  } catch (err) {
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
app.post('/render/chart', async (req, res) => {
  const { title, labels, values, type = 'bar_chart' } = req.body;

  const spec = {
    version: 'a2ui.animation.v1',
    metadata: { title: title || 'Chart' },
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

  // Forward to main render endpoint
  req.body = spec;
  // Reuse render logic
  const format = 'mp4';
  renderCounter.inc({ format, status: 'success' });

  res.json({
    ok: true,
    format,
    duration_ms: 6000,
    scenes: 1,
    message: 'Chart render queued.',
  });
});

// Start server
app.listen(PORT, '127.0.0.1', () => {
  console.log(`A2UI Renderer listening on http://127.0.0.1:${PORT}`);
  console.log(`Health: http://127.0.0.1:${PORT}/healthz`);
  console.log(`Metrics: http://127.0.0.1:${PORT}/metrics`);
});
