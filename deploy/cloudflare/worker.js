/**
 * PMOVES.AI CI/CD Orchestrator - Cloudflare Worker
 *
 * Purpose:
 * - Receives GitHub webhook events (push, PR, workflow_dispatch)
 * - Analyzes changes and routes builds to optimal runners:
 *   - GPU builds -> AI Lab (self-hosted)
 *   - VPS deploys -> cloudstartup/kvm4 (self-hosted)
 *   - Lightweight tasks -> GitHub hosted or Cloudflare edge
 * - Tracks build state in KV
 * - Sends notifications to Discord
 *
 * NOT a GitHub Actions runner replacement - this is an orchestration layer
 * that intelligently routes CI/CD jobs to the best runner based on requirements.
 */

import crypto from 'crypto';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check endpoint
    if (url.pathname === '/health' && request.method === 'GET') {
      return new Response(JSON.stringify({
        status: 'healthy',
        service: 'pmoves-ci-orchestrator',
        mode: env.RUNNER_DISPATCH_MODE || 'hybrid',
        timestamp: new Date().toISOString()
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // GitHub webhook endpoint
    if (url.pathname === '/webhook/github' && request.method === 'POST') {
      return handleGitHubWebhook(request, env, ctx);
    }

    // Build status query endpoint
    if (url.pathname === '/status' && request.method === 'GET') {
      const buildId = url.searchParams.get('build_id');
      if (!buildId) {
        return new Response('Missing build_id parameter', { status: 400 });
      }
      return getBuildStatus(buildId, env);
    }

    // Metrics endpoint for Prometheus scraping
    if (url.pathname === '/metrics' && request.method === 'GET') {
      return getMetrics(env);
    }

    return new Response('PMOVES.AI CI/CD Orchestrator', {
      status: 200,
      headers: { 'Content-Type': 'text/plain' }
    });
  }
};

/**
 * Verify GitHub webhook signature
 */
async function verifyGitHubSignature(request, secret) {
  const signature = request.headers.get('X-Hub-Signature-256');
  if (!signature) return false;

  const body = await request.text();
  const expectedSignature = 'sha256=' +
    crypto.createHmac('sha256', secret)
      .update(body)
      .digest('hex');

  return signature === expectedSignature;
}

/**
 * Handle GitHub webhook events
 */
async function handleGitHubWebhook(request, env, ctx) {
  // Verify signature if webhook secret is configured
  if (env.WEBHOOK_SECRET) {
    const clonedRequest = request.clone();
    const isValid = await verifyGitHubSignature(clonedRequest, env.WEBHOOK_SECRET);
    if (!isValid) {
      return new Response('Invalid signature', { status: 401 });
    }
  }

  const event = request.headers.get('X-GitHub-Event');
  const payload = await request.json();

  console.log(`Received GitHub event: ${event}`);

  let response;
  switch (event) {
    case 'push':
      response = await handlePushEvent(payload, env);
      break;
    case 'pull_request':
      response = await handlePullRequestEvent(payload, env);
      break;
    case 'workflow_dispatch':
      response = await handleWorkflowDispatchEvent(payload, env);
      break;
    case 'workflow_run':
      response = await handleWorkflowRunEvent(payload, env);
      break;
    default:
      response = { status: 'ignored', event };
  }

  // Store build state in KV
  if (response.build_id) {
    await env.CI_STATE.put(
      `build:${response.build_id}`,
      JSON.stringify(response),
      { expirationTtl: 86400 } // 24 hours
    );
  }

  // Send Discord notification if configured
  if (env.DISCORD_WEBHOOK_URL && response.notify) {
    ctx.waitUntil(sendDiscordNotification(response, env.DISCORD_WEBHOOK_URL));
  }

  return new Response(JSON.stringify(response), {
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Analyze push event and determine runner strategy
 */
async function handlePushEvent(payload, env) {
  const { repository, ref, commits } = payload;
  const branch = ref.replace('refs/heads/', '');

  // Analyze changed files to determine build requirements
  const changedFiles = commits.flatMap(c => [
    ...(c.added || []),
    ...(c.modified || []),
    ...(c.removed || [])
  ]);

  const analysis = analyzeChanges(changedFiles);
  const runnerStrategy = determineRunnerStrategy(analysis, env.RUNNER_DISPATCH_MODE);

  return {
    build_id: generateBuildId(),
    event: 'push',
    repository: repository.full_name,
    branch,
    commit: payload.after,
    analysis,
    runner_strategy: runnerStrategy,
    timestamp: new Date().toISOString(),
    notify: runnerStrategy.requires_gpu || branch === 'main'
  };
}

/**
 * Handle pull request events
 */
async function handlePullRequestEvent(payload, env) {
  const { action, pull_request, repository } = payload;

  if (!['opened', 'synchronize', 'reopened'].includes(action)) {
    return { status: 'ignored', action };
  }

  const changedFiles = []; // Would need to fetch via GitHub API
  const analysis = analyzeChanges(changedFiles);
  const runnerStrategy = determineRunnerStrategy(analysis, env.RUNNER_DISPATCH_MODE);

  return {
    build_id: generateBuildId(),
    event: 'pull_request',
    action,
    repository: repository.full_name,
    pr_number: pull_request.number,
    branch: pull_request.head.ref,
    analysis,
    runner_strategy: runnerStrategy,
    timestamp: new Date().toISOString(),
    notify: false
  };
}

/**
 * Handle manual workflow dispatch
 */
async function handleWorkflowDispatchEvent(payload, env) {
  const { repository, ref, inputs } = payload;

  return {
    build_id: generateBuildId(),
    event: 'workflow_dispatch',
    repository: repository.full_name,
    ref,
    inputs,
    runner_strategy: {
      type: 'manual',
      runner: inputs?.runner || 'github-hosted'
    },
    timestamp: new Date().toISOString(),
    notify: true
  };
}

/**
 * Handle workflow run completion
 */
async function handleWorkflowRunEvent(payload, env) {
  const { action, workflow_run, repository } = payload;

  if (action !== 'completed') {
    return { status: 'ignored', action };
  }

  return {
    build_id: workflow_run.id.toString(),
    event: 'workflow_run',
    action,
    repository: repository.full_name,
    workflow: workflow_run.name,
    conclusion: workflow_run.conclusion,
    duration: workflow_run.updated_at - workflow_run.created_at,
    runner: workflow_run.runner_name,
    timestamp: new Date().toISOString(),
    notify: workflow_run.conclusion === 'failure'
  };
}

/**
 * Analyze changed files to determine build requirements
 */
function analyzeChanges(files) {
  const analysis = {
    requires_gpu: false,
    requires_docker: false,
    is_lightweight: true,
    services_affected: [],
    estimated_duration_seconds: 120
  };

  for (const file of files) {
    // GPU-intensive paths
    if (file.includes('ollama') ||
        file.includes('Dockerfile.cuda') ||
        file.includes('Dockerfile.gpu') ||
        file.includes('hirag-gateway')) {
      analysis.requires_gpu = true;
      analysis.is_lightweight = false;
      analysis.estimated_duration_seconds = 1800; // 30 minutes
    }

    // Docker builds
    if (file.includes('Dockerfile') ||
        file.includes('docker-compose')) {
      analysis.requires_docker = true;
      analysis.is_lightweight = false;
    }

    // Service changes
    if (file.startsWith('pmoves/services/')) {
      const service = file.split('/')[2];
      if (!analysis.services_affected.includes(service)) {
        analysis.services_affected.push(service);
      }
    }

    // Documentation-only changes
    if (file.endsWith('.md') ||
        file.includes('docs/') ||
        file.includes('.github/')) {
      // Keep is_lightweight = true
    } else {
      analysis.is_lightweight = false;
    }
  }

  return analysis;
}

/**
 * Determine optimal runner strategy based on analysis
 */
function determineRunnerStrategy(analysis, mode = 'hybrid') {
  // Force mode override
  if (mode === 'self-hosted-only') {
    return {
      type: 'self-hosted',
      runner: analysis.requires_gpu ? 'ai-lab' : 'vps',
      labels: analysis.requires_gpu
        ? ['self-hosted', 'ai-lab', 'gpu']
        : ['self-hosted', 'vps'],
      reason: 'Forced self-hosted mode'
    };
  }

  if (mode === 'cloudflare-only') {
    return {
      type: 'github-hosted',
      runner: 'ubuntu-latest',
      labels: ['ubuntu-latest'],
      reason: 'Cloudflare mode - using GitHub hosted for compute'
    };
  }

  // Hybrid mode (intelligent routing)

  // GPU builds MUST use AI Lab
  if (analysis.requires_gpu) {
    return {
      type: 'self-hosted',
      runner: 'ai-lab',
      labels: ['self-hosted', 'ai-lab', 'gpu'],
      reason: 'GPU required',
      estimated_cost: 0, // Self-hosted
      estimated_duration: analysis.estimated_duration_seconds
    };
  }

  // Docker builds prefer self-hosted for persistent cache
  if (analysis.requires_docker && analysis.services_affected.length > 0) {
    return {
      type: 'self-hosted',
      runner: 'vps',
      labels: ['self-hosted', 'vps'],
      reason: 'Docker build with layer cache',
      estimated_cost: 0,
      estimated_duration: 600
    };
  }

  // Lightweight tasks use GitHub hosted (cheaper than maintaining idle self-hosted)
  if (analysis.is_lightweight) {
    return {
      type: 'github-hosted',
      runner: 'ubuntu-latest',
      labels: ['ubuntu-latest'],
      reason: 'Lightweight task - GitHub hosted more efficient',
      estimated_cost: 0.008, // ~$0.008/minute
      estimated_duration: 120
    };
  }

  // Default to self-hosted VPS for everything else
  return {
    type: 'self-hosted',
    runner: 'vps',
    labels: ['self-hosted', 'vps'],
    reason: 'Default VPS routing',
    estimated_cost: 0,
    estimated_duration: 300
  };
}

/**
 * Get build status from KV
 */
async function getBuildStatus(buildId, env) {
  const buildData = await env.CI_STATE.get(`build:${buildId}`);

  if (!buildData) {
    return new Response(JSON.stringify({ error: 'Build not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  return new Response(buildData, {
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Get metrics for Prometheus
 */
async function getMetrics(env) {
  // In production, would aggregate from KV
  const metrics = `
# HELP pmoves_ci_builds_total Total number of CI builds processed
# TYPE pmoves_ci_builds_total counter
pmoves_ci_builds_total 0

# HELP pmoves_ci_runner_assignments Runner assignment counts by type
# TYPE pmoves_ci_runner_assignments counter
pmoves_ci_runner_assignments{runner="ai-lab"} 0
pmoves_ci_runner_assignments{runner="vps"} 0
pmoves_ci_runner_assignments{runner="github-hosted"} 0
  `.trim();

  return new Response(metrics, {
    headers: { 'Content-Type': 'text/plain' }
  });
}

/**
 * Send notification to Discord
 */
async function sendDiscordNotification(buildInfo, webhookUrl) {
  const embed = {
    title: `CI Build: ${buildInfo.event}`,
    description: `Repository: ${buildInfo.repository}`,
    color: buildInfo.conclusion === 'failure' ? 0xff0000 : 0x00ff00,
    fields: [
      {
        name: 'Runner Strategy',
        value: buildInfo.runner_strategy.reason || 'N/A',
        inline: true
      },
      {
        name: 'Runner Type',
        value: buildInfo.runner_strategy.runner || 'N/A',
        inline: true
      }
    ],
    timestamp: buildInfo.timestamp
  };

  await fetch(webhookUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ embeds: [embed] })
  });
}

/**
 * Generate unique build ID
 */
function generateBuildId() {
  return `build-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
