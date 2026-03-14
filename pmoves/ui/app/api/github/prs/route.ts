/* ═══════════════════════════════════════════════════════════════════════════
   API: GitHub Pull Requests
   Fetches PR status for POWERFULMOVES repositories via GitHub REST API
   ═══════════════════════════════════════════════════════════════════════════ */

import { NextRequest, NextResponse } from 'next/server';
import type { PRListResponse, PRStatus, PRState } from '@/lib/types/github';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

/**
 * GitHub repository configuration
 */
const GITHUB_ORG = 'POWERFULMOVES';
const MAIN_REPOS = ['PMOVES.AI', 'PMOVES-BoTZ', 'PMOVES-Archon', 'PMOVES-HiRAG', 'PMOVES-Agent-Zero'];

/**
 * Map GitHub GraphQL state to our type
 */
function mapState(state: string): PRState {
  switch (state.toUpperCase()) {
    case 'OPEN':
      return 'OPEN';
    case 'CLOSED':
      return 'CLOSED';
    case 'MERGED':
      return 'MERGED';
    case 'DRAFT':
      return 'DRAFT';
    default:
      return 'OPEN';
  }
}

/**
 * Fetch PRs from a single repository via GitHub GraphQL API
 */
async function fetchRepoPRs(
  repo: string,
  token: string,
  states: PRState[] = ['OPEN', 'DRAFT']
): Promise<PRStatus[]> {
  const stateFilter = states.includes('MERGED') ? 'MERGED' : states.includes('CLOSED') ? 'CLOSED' : 'OPEN';

  // Use GitHub REST API for simplicity (no GraphQL complexity)
  const url = `https://api.github.com/repos/${GITHUB_ORG}/${repo}/pulls?state=${stateFilter}&per_page=100&sort=updated&direction=desc`;

  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    console.error(`GitHub API error for ${repo}:`, response.status, response.statusText);
    return [];
  }

  const data = await response.json();

  return data.map((pr: any) => ({
    number: pr.number,
    title: pr.title,
    state: mapState(pr.state),
    isDraft: pr.draft,
    author: pr.user.login,
    avatarUrl: pr.user.avatar_url,
    createdAt: pr.created_at,
    updatedAt: pr.updated_at,
    closedAt: pr.closed_at,
    mergedAt: pr.merged_at,
    url: pr.html_url,
    baseBranch: pr.base.ref,
    headBranch: pr.head.ref,
    additions: pr.additions,
    deletions: pr.deletions,
    changedFiles: pr.changed_files,
    commentCount: pr.comments || 0,
    reviewCount: pr.review_comments || 0,
    statusCheckRollup: pr.statuses_url ? undefined : undefined, // Would need separate fetch
    labels: pr.labels?.map((l: any) => l.name) || [],
    repository: repo,
  }));
}

/**
 * Get or mint GitHub App installation token
 */
async function getGitHubToken(): Promise<string | null> {
  // Try to get token from Archon service which has minting capability
  try {
    const archonResponse = await fetch('http://localhost:8091/api/github/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(5000),
    });

    if (archonResponse.ok) {
      const data = await archonResponse.json();
      return data.token;
    }
  } catch (_e) {
    // Archon service unavailable - return null to trigger fallback
  }

  return null;
}

/**
 * GET /api/github/prs
 *
 * Query params:
 *   - state: Filter by state (OPEN, CLOSED, MERGED, DRAFT) - default: OPEN,DRAFT
 *   - repo: Filter by repository name
 *   - limit: Max results to return (default: 50)
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const stateParam = searchParams.get('state')?.toUpperCase().split(',') || ['OPEN', 'DRAFT'];
  const repoFilter = searchParams.get('repo');
  const limitParam = searchParams.get('limit');
  const limitParsed = parseInt(limitParam || '50', 10);
  const limit = isNaN(limitParsed) ? 50 : Math.min(limitParsed, 100);

  const states: PRState[] = stateParam.filter((s): s is PRState =>
    ['OPEN', 'CLOSED', 'MERGED', 'DRAFT'].includes(s)
  ) as PRState[];

  try {
    // Get GitHub token from Archon or use fallback
    const token = await getGitHubToken();

    if (!token) {
      return NextResponse.json(
        {
          error: 'GitHub token unavailable',
          message: 'Archon service unavailable or GitHub App not configured',
          items: [],
          timestamp: new Date().toISOString(),
          total: 0,
        },
        { status: 503 }
      );
    }

    // Fetch PRs from all configured repos (or single repo if filtered)
    const reposToQuery = repoFilter ? [repoFilter] : MAIN_REPOS;
    const prPromises = reposToQuery.map((repo) => fetchRepoPRs(repo, token, states));

    const prArrays = await Promise.all(prPromises);
    const allPrs = prArrays.flat();

    // Sort by updated date and apply limit
    const sortedPrs = allPrs
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, limit);

    // Calculate statistics
    const total = sortedPrs.length;
    const open = sortedPrs.filter((pr) => pr.state === 'OPEN').length;
    const merged = sortedPrs.filter((pr) => pr.state === 'MERGED').length;
    const closed = sortedPrs.filter((pr) => pr.state === 'CLOSED').length;
    const draft = sortedPrs.filter((pr) => pr.state === 'DRAFT' || pr.isDraft).length;

    const response: PRListResponse = {
      items: sortedPrs,
      timestamp: new Date().toISOString(),
      total,
      open,
      merged,
      closed,
      draft,
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
      },
    });

  } catch (error) {
    return NextResponse.json(
      {
        error: 'Failed to fetch pull requests',
        message: error instanceof Error ? error.message : String(error),
        items: [],
        timestamp: new Date().toISOString(),
        total: 0,
        open: 0,
        merged: 0,
        closed: 0,
        draft: 0,
      },
      { status: 500 }
    );
  }
}
