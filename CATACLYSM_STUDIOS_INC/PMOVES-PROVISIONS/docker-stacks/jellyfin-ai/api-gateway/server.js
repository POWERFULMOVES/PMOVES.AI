
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const { createClient } = require('@supabase/supabase-js');
const neo4j = require('neo4j-driver');
const Redis = require('redis');
const axios = require('axios');
const WebSocket = require('ws');
const fs = require('fs/promises');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Honor reverse proxy headers so rate limiting sees real client IPs.
app.set('trust proxy', true);

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3001'],
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use(limiter);

// Logging
app.use(morgan('combined'));

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Initialize clients
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

const neo4jDriver = neo4j.driver(
  process.env.NEO4J_URI,
  neo4j.auth.basic(process.env.NEO4J_USER, process.env.NEO4J_PASSWORD)
);

const redisClient = Redis.createClient({
  url: process.env.REDIS_URL || 'redis://redis:6379'
});

redisClient.connect().catch((err) => {
  console.error('Redis connection error:', err);
});

const MIGRATION_RESULTS_KEY = process.env.MIGRATION_RESULTS_KEY || 'jellyfin:migration:runs';
const MIGRATION_RESULTS_PATH = process.env.MIGRATION_RESULTS_PATH;
const BRIDGE_LOG_PATH = process.env.BRIDGE_LOG_PATH;
const PUBLISHER_LOG_PATH = process.env.PUBLISHER_LOG_PATH;
const BRIDGE_LOG_KEY = process.env.BRIDGE_LOG_KEY || 'logs:jellyfin-bridge';
const PUBLISHER_LOG_KEY = process.env.PUBLISHER_LOG_KEY || 'logs:publisher';
const LOG_EXCERPT_LINES = parseInt(process.env.LOG_EXCERPT_LINES || '200', 10);

async function readJsonFile(filePath) {
  if (!filePath) return null;
  try {
    const resolved = path.resolve(filePath);
    const raw = await fs.readFile(resolved, 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return null;
    }
    console.error('Failed to read migration results file:', error);
    throw error;
  }
}

async function safeRedisListFetch(key, start = 0, end = -1) {
  if (!redisClient?.isOpen) return [];
  try {
    return await redisClient.lRange(key, start, end);
  } catch (error) {
    console.warn(`Redis read failed for key ${key}:`, error.message);
    return [];
  }
}

function normalizeMigrationResult(payload) {
  if (!payload) return null;

  if (Array.isArray(payload)) {
    return normalizeMigrationResult(payload[0]);
  }

  if (payload?.runs && Array.isArray(payload.runs)) {
    const sorted = [...payload.runs].sort((a, b) => {
      const aTime = new Date(a.completed_at || a.created_at || a.timestamp || 0).getTime();
      const bTime = new Date(b.completed_at || b.created_at || b.timestamp || 0).getTime();
      return bTime - aTime;
    });
    return normalizeMigrationResult(sorted[0]);
  }

  return payload;
}

function deriveChecklist(migrationResult) {
  if (!migrationResult) {
    return [
      {
        id: 'supabase-migrations',
        label: 'Supabase migrations applied',
        completed: false,
        detail: 'Awaiting latest migration run.'
      },
      {
        id: 'neo4j-sync',
        label: 'Neo4j media graph refreshed',
        completed: false
      },
      {
        id: 'bridge-health',
        label: 'Jellyfin bridge responding',
        completed: false
      },
      {
        id: 'publisher-health',
        label: 'Publisher webhooks draining queue',
        completed: false
      }
    ];
  }

  if (Array.isArray(migrationResult.checklist)) {
    return migrationResult.checklist.map((item, index) => ({
      id: item.id || `check-${index}`,
      label: item.label || item.name || `Check ${index + 1}`,
      completed: item.completed ?? item.status === 'ok' ?? false,
      detail: item.detail || item.notes || null
    }));
  }

  const checklist = [];
  const supabaseStatus = migrationResult.supabase?.status || migrationResult.supabase_status;
  const neo4jStatus = migrationResult.neo4j?.status || migrationResult.neo4j_status;
  const bridgeStatus = migrationResult.bridge?.status || migrationResult.bridge_status;
  const publisherStatus = migrationResult.publisher?.status || migrationResult.publisher_status;

  checklist.push({
    id: 'supabase-migrations',
    label: 'Supabase migrations applied',
    completed: (supabaseStatus || '').toLowerCase() === 'ok'
  });
  checklist.push({
    id: 'neo4j-sync',
    label: 'Neo4j media graph refreshed',
    completed: (neo4jStatus || '').toLowerCase() === 'ok'
  });
  checklist.push({
    id: 'bridge-health',
    label: 'Jellyfin bridge responding',
    completed: (bridgeStatus || '').toLowerCase() === 'ok'
  });
  checklist.push({
    id: 'publisher-health',
    label: 'Publisher webhooks draining queue',
    completed: (publisherStatus || '').toLowerCase() === 'ok'
  });

  return checklist;
}

function deriveWebhookLatency(migrationResult) {
  if (!migrationResult) return null;

  if (migrationResult.metrics?.webhookLatency) {
    return migrationResult.metrics.webhookLatency;
  }

  if (migrationResult.webhookLatency) {
    return migrationResult.webhookLatency;
  }

  const latencyFields = ['webhook_latency_ms', 'webhook_latency'];
  for (const field of latencyFields) {
    if (field in migrationResult) {
      return {
        averageMs: Number(migrationResult[field]) || null
      };
    }
  }

  return null;
}

async function fetchLatestMigrationResult() {
  const [redisEntry] = await safeRedisListFetch(MIGRATION_RESULTS_KEY, 0, 0);

  if (redisEntry) {
    try {
      const parsed = JSON.parse(redisEntry);
      return normalizeMigrationResult(parsed);
    } catch (error) {
      console.warn('Failed to parse migration result from Redis:', error.message);
    }
  }

  const filePayload = await readJsonFile(MIGRATION_RESULTS_PATH);
  if (filePayload) {
    return normalizeMigrationResult(filePayload);
  }

  return null;
}

async function tailFile(filePath, lines) {
  if (!filePath) return null;
  try {
    const resolved = path.resolve(filePath);
    const contents = await fs.readFile(resolved, 'utf8');
    const entries = contents.split(/\r?\n/).filter(Boolean);
    return entries.slice(-lines);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return null;
    }
    console.error(`Failed to read log file at ${filePath}:`, error);
    throw error;
  }
}

async function getLogExcerpt(options = {}, lines = LOG_EXCERPT_LINES) {
  const { filePath, redisKey } = options;
  const redisEntries = redisKey ? await safeRedisListFetch(redisKey, 0, lines - 1) : [];

  if (redisEntries.length) {
    return { source: 'redis', entries: redisEntries };
  }

  const fileEntries = await tailFile(filePath, lines);
  if (fileEntries && fileEntries.length) {
    return { source: 'file', entries: fileEntries };
  }

  return { source: redisEntries.length ? 'redis' : 'file', entries: [] };
}

// WebSocket server for real-time updates
const wss = new WebSocket.Server({ port: 3002 });

wss.on('connection', (ws) => {
  console.log('Client connected to WebSocket');

  ws.on('close', () => {
    console.log('Client disconnected from WebSocket');
  });
});

// Broadcast to all connected clients
function broadcast(data) {
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  });
}

// Routes

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Get media library with analysis
app.get('/api/media', async (req, res) => {
  try {
    const { page = 1, limit = 20, type, genre } = req.query;
    const offset = (page - 1) * limit;

    let query = supabase
      .from('media')
      .select(`
        *,
        media_analysis (
          ai_description,
          ai_analysis,
          audio_features
        )
      `)
      .range(offset, offset + limit - 1);

    if (type) query = query.eq('type', type);

    const { data, error } = await query;

    if (error) throw error;

    res.json({
      data,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total: data.length
      }
    });

  } catch (error) {
    console.error('Error fetching media:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get media item details
app.get('/api/media/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const { data, error } = await supabase
      .from('media')
      .select(`
        *,
        media_analysis (*)
      `)
      .eq('id', id)
      .single();

    if (error) throw error;

    res.json(data);

  } catch (error) {
    console.error('Error fetching media item:', error);
    res.status(500).json({ error: error.message });
  }
});

// Search media using Neo4j
app.get('/api/search', async (req, res) => {
  try {
    const { q, type = 'similarity' } = req.query;

    if (!q) {
      return res.status(400).json({ error: 'Query parameter required' });
    }

    const session = neo4jDriver.session();

    let cypher;
    if (type === 'similarity') {
      cypher = `
        MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
        WHERE a.ai_description CONTAINS $query OR m.name CONTAINS $query
        RETURN m, a
        LIMIT 20
      `;
    } else {
      cypher = `
        MATCH (m:Media)
        WHERE m.name CONTAINS $query
        RETURN m
        LIMIT 20
      `;
    }

    const result = await session.run(cypher, { query: q });
    const records = result.records.map(record => ({
      media: record.get('m').properties,
      analysis: record.has('a') ? record.get('a').properties : null
    }));

    await session.close();

    res.json({ results: records, query: q });

  } catch (error) {
    console.error('Error searching:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get recommendations based on audio features
app.get('/api/recommendations/:mediaId', async (req, res) => {
  try {
    const { mediaId } = req.params;

    const session = neo4jDriver.session();

    const cypher = `
      MATCH (m:Media {id: $mediaId})-[:HAS_FEATURES]->(f:AudioFeatures)
      MATCH (other:Media)-[:HAS_FEATURES]->(otherF:AudioFeatures)
      WHERE m.id <> other.id
      WITH m, other, 
           abs(f.tempo - otherF.tempo) as tempoDiff,
           abs(f.spectral_centroid_mean - otherF.spectral_centroid_mean) as spectralDiff
      WHERE tempoDiff < 20 AND spectralDiff < 1000
      RETURN other
      ORDER BY tempoDiff + spectralDiff
      LIMIT 10
    `;

    const result = await session.run(cypher, { mediaId });
    const recommendations = result.records.map(record => 
      record.get('other').properties
    );

    await session.close();

    res.json({ recommendations });

  } catch (error) {
    console.error('Error getting recommendations:', error);
    res.status(500).json({ error: error.message });
  }
});

// Trigger analysis for specific media
app.post('/api/analyze/:mediaId', async (req, res) => {
  try {
    const { mediaId } = req.params;

    // Add to processing queue
    await redisClient.lPush('analysis_queue', mediaId);

    // Broadcast update
    broadcast({
      type: 'analysis_queued',
      mediaId,
      timestamp: new Date().toISOString()
    });

    res.json({ message: 'Analysis queued', mediaId });

  } catch (error) {
    console.error('Error queueing analysis:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get analytics dashboard data
app.get('/api/analytics', async (req, res) => {
  try {
    const session = neo4jDriver.session();

    // Get various analytics
    const queries = {
      totalMedia: `MATCH (m:Media) RETURN count(m) as count`,
      analyzedMedia: `MATCH (m:Media)-[:HAS_ANALYSIS]->() RETURN count(m) as count`,
      avgTempo: `MATCH ()-[:HAS_FEATURES]->(f:AudioFeatures) RETURN avg(f.tempo) as avg`,
      genreDistribution: `
        MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
        RETURN a.ai_analysis.genre as genre, count(*) as count
        ORDER BY count DESC
        LIMIT 10
      `
    };

    const results = {};

    for (const [key, query] of Object.entries(queries)) {
      const result = await session.run(query);
      results[key] = result.records.map(record => 
        Object.fromEntries(record.keys.map(key => [key, record.get(key)]))
      );
    }

    await session.close();

    res.json(results);

  } catch (error) {
    console.error('Error getting analytics:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/migrations/latest', async (req, res) => {
  try {
    const migrationResult = await fetchLatestMigrationResult();
    const checklist = deriveChecklist(migrationResult);
    const webhookLatency = deriveWebhookLatency(migrationResult);

    res.json({
      run: migrationResult,
      checklist,
      webhookLatency,
      source: migrationResult ? 'available' : 'unavailable'
    });
  } catch (error) {
    console.error('Error fetching migration results:', error);
    res.status(500).json({ error: 'Failed to load migration results' });
  }
});

app.get('/api/logs/:service', async (req, res) => {
  const { service } = req.params;
  const lines = parseInt(req.query.lines, 10) || LOG_EXCERPT_LINES;

  const config = {
    bridge: { filePath: BRIDGE_LOG_PATH, redisKey: BRIDGE_LOG_KEY },
    publisher: { filePath: PUBLISHER_LOG_PATH, redisKey: PUBLISHER_LOG_KEY }
  }[service];

  if (!config) {
    return res.status(404).json({ error: 'Unknown log service requested' });
  }

  try {
    const excerpt = await getLogExcerpt(config, lines);
    res.json({
      service,
      lines,
      entries: excerpt.entries,
      source: excerpt.source
    });
  } catch (error) {
    console.error(`Error fetching ${service} logs:`, error);
    res.status(500).json({ error: `Failed to load ${service} logs` });
  }
});

// Export data for content creation
app.get('/api/export/:format', async (req, res) => {
  try {
    const { format } = req.params;
    const { mediaIds } = req.query;

    if (!mediaIds) {
      return res.status(400).json({ error: 'mediaIds required' });
    }

    const ids = mediaIds.split(',');

    const { data, error } = await supabase
      .from('media')
      .select(`
        *,
        media_analysis (*)
      `)
      .in('id', ids);

    if (error) throw error;

    if (format === 'json') {
      res.json(data);
    } else if (format === 'csv') {
      // Simple CSV export
      const csv = data.map(item => 
        `"${item.name}","${item.type}","${item.media_analysis?.[0]?.ai_description || ''}"`
      ).join('\n');

      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', 'attachment; filename="media_export.csv"');
      res.send(`Name,Type,Description\n${csv}`);
    } else {
      res.status(400).json({ error: 'Unsupported format' });
    }

  } catch (error) {
    console.error('Error exporting data:', error);
    res.status(500).json({ error: error.message });
  }
});

// YouTube integration for content creation
app.post('/api/youtube/analyze', async (req, res) => {
  try {
    const { videoUrl, mediaIds } = req.body;

    if (!videoUrl || !mediaIds) {
      return res.status(400).json({ error: 'videoUrl and mediaIds required' });
    }

    // Get media analysis for comparison
    const { data, error } = await supabase
      .from('media')
      .select(`
        *,
        media_analysis (*)
      `)
      .in('id', mediaIds);

    if (error) throw error;

    // This would integrate with YouTube API and AI analysis
    // For now, return structured data for content creation
    const contentSuggestions = {
      videoUrl,
      relatedMedia: data,
      suggestions: {
        title: `Music Analysis: ${data.length} Tracks Compared`,
        description: `Analysis of ${data.map(m => m.name).join(', ')}`,
        tags: [...new Set(data.flatMap(m => 
          m.media_analysis?.[0]?.ai_analysis?.tags || []
        ))],
        timestamps: data.map((m, i) => ({
          time: `${i * 30}:00`,
          description: m.media_analysis?.[0]?.ai_description || m.name
        }))
      }
    };

    res.json(contentSuggestions);

  } catch (error) {
    console.error('Error analyzing for YouTube:', error);
    res.status(500).json({ error: error.message });
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error('API Error:', error);
  res.status(500).json({ 
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? error.message : undefined
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

// Start server
app.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
  console.log(`WebSocket server running on port 3002`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Shutting down gracefully...');
  await neo4jDriver.close();
  await redisClient.disconnect();
  process.exit(0);
});
