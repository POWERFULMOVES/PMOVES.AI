/* ═══════════════════════════════════════════════════════════════════════════
   GitHub Pull Request Types
   TypeScript types for GitHub PR status dashboard integration
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * GitHub pull request state
 */
export type PRState = 'OPEN' | 'CLOSED' | 'MERGED' | 'DRAFT';

/**
 * GitHub pull request review state
 */
export type PRReviewState = 'APPROVED' | 'CHANGES_REQUESTED' | 'COMMENTED' | 'PENDING' | 'DISMISSED';

/**
 * GitHub user information
 */
export interface GitHubUser {
  login: string;
  name?: string;
  avatarUrl?: string;
  url?: string;
}

/**
 * GitHub pull request from API/gh CLI
 */
export interface GitHubPullRequest {
  number: number;
  title: string;
  body?: string;
  state: PRState;
  isDraft: boolean;
  author: GitHubUser;
  createdAt: string;
  updatedAt: string;
  closedAt?: string;
  mergedAt?: string;
  url: string;
  headRefName: string;
  baseRefName: string;
  headRepository?: {
    name: string;
    owner: GitHubUser;
  };
  additions: number;
  deletions: number;
  changedFiles: number;
  comments: {
    totalCount: number;
  };
  reviews?: {
    totalCount: number;
  };
  statusCheckRollup?: {
    state?: 'SUCCESS' | 'FAILURE' | 'PENDING' | 'EXPECTED';
  };
  labels?: {
    nodes: Array<{
      name: string;
      color: string;
    }>;
  };
}

/**
 * PR status for dashboard display
 */
export interface PRStatus {
  number: number;
  title: string;
  state: PRState;
  isDraft: boolean;
  author: string;
  avatarUrl?: string;
  createdAt: string;
  updatedAt: string;
  url: string;
  baseBranch: string;
  headBranch: string;
  additions: number;
  deletions: number;
  changedFiles: number;
  commentCount: number;
  reviewCount: number;
  statusCheckRollup?: string;
  labels: string[];
  repository?: string;
}

/**
 * PR list response from API
 */
export interface PRListResponse {
  items: PRStatus[];
  timestamp: string;
  total: number;
  open: number;
  merged: number;
  closed: number;
  draft: number;
}

/**
 * Filter options for PR queries
 */
export interface PRFilterOptions {
  state?: PRState | PRState[];
  author?: string;
  baseBranch?: string;
  labels?: string[];
  repository?: string;
  limit?: number;
}

/**
 * Sort options for PR queries
 */
export type PRSortField = 'created' | 'updated' | 'comments' | 'additions' | 'deletions';
export type PRSortDirection = 'asc' | 'desc';

export interface PRSortOptions {
  field: PRSortField;
  direction: PRSortDirection;
}
