# PMOVES UI Integration Features - Complete Reference

**Status:** Phase 1 Complete | Phases 2-6 Pending
**Created:** 2025-12-27
**Branch:** `feat/ui-integrations-search-jellyfin-research`

---

## Quick Reference Dashboard

| Phase | Feature | Status | Priority |
|-------|---------|--------|----------|
| 1 | Foundation (Navigation, API Clients, Pages) | ✅ Complete | Required |
| 2 | Search Interface (Hi-RAG v2) | ✅ Complete | High |
| 3 | Jellyfin Integration | 🔄 In Progress | Medium |
| 4 | Deep Research Dashboard | ⏳ Pending | High |
| 5 | Enhanced Video Approval | ⏳ Pending | Medium |
| 6 | Integration & Testing | ⏳ Pending | Required |

---

## Development Patterns Reference

### Error Handling Pattern
```typescript
// Use Result<T, E> type for all API responses
import { Result, ok, err } from '../errorUtils';

async function apiCall(): Promise<Result<Data, string>> {
  try {
    const response = await fetch(/* ... */);
    if (!response.ok) {
      return err(getErrorMessage(response.status));
    }
    return ok(await response.json());
  } catch (error) {
    logError('Operation failed', error, 'error', { component: 'name' });
    return err(String(error));
  }
}
```

### Authentication Pattern
```typescript
// User identity from JWT only - NEVER from request body/query
function ownerFromJwt(token: string): string {
  // Decode and validate JWT
  // Return user ID from token payload
}
```

### HTTP Status Codes
- **401** - Authentication failure
- **400** - Bad request (validation errors)
- **500** - Server error

### Accessibility (WCAG 2.1)
```tsx
// Skip link pattern
<a
  href="#main"
  className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4"
>
  Skip to main content
</a>

// ARIA live regions
<div aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>
```

### Tailwind JIT Static Classes
```tsx
// DON'T - dynamic class interpolation
className={`bg-${color}-100`}

// DO - static lookup objects
const colorClasses = {
  blue: 'bg-blue-100',
  red: 'bg-red-100',
};
className={colorClasses[color]}
```

---

## Phase 1: Foundation ✅ COMPLETED

### Checklist
- [x] Update navigation with new routes (search, jellyfin, research)
- [x] Create API client functions (`lib/api/`)
- [x] Create dashboard placeholder pages
- [x] Commit and push changes

### Completed Files

**Navigation:** `pmoves/ui/components/DashboardNavigation.tsx`
```tsx
// Added navigation items:
{ href: '/dashboard/search', label: 'Search', key: 'search', accent: 'forest' },
{ href: '/dashboard/jellyfin', label: 'Jellyfin', key: 'jellyfin', accent: 'violet' },
{ href: '/dashboard/research', label: 'Research', key: 'research', accent: 'gold' },
```

**API Client:** `pmoves/ui/lib/api/hirag.ts`
```typescript
export async function hiragQuery(
  query: string,
  options?: { top_k?: number; rerank?: boolean }
): Promise<Result<HiragResult[], string>>

export async function hiragHealth(): Promise<Result<{healthy: boolean}, string>>
```

**API Client:** `pmoves/ui/lib/api/jellyfin.ts`
```typescript
export async function jellyfinSearch(term: string): Promise<Result<JellyfinItem[], string>>
export async function jellyfinSyncStatus(): Promise<Result<JellyfinSyncStatusInfo, string>>
export async function linkJellyfinItem(videoId: string, jellyfinId: string): Promise<Result<void, string>>
export async function triggerJellyfinSync(): Promise<Result<void, string>>
export async function triggerBackfill(options: {limit?: number}): Promise<Result<void, string>>
```

**API Client:** `pmoves/ui/lib/api/research.ts`
```typescript
export async function initiateResearch(
  query: string,
  options?: ResearchOptions
): Promise<Result<ResearchTask, string>>

export async function listResearchTasks(options?: {
  status?: ResearchStatus;
  limit?: number;
}): Promise<Result<ResearchTask[], string>>

export async function getResearchResults(taskId: string): Promise<Result<ResearchResult, string>>
export async function cancelResearch(taskId: string): Promise<Result<void, string>>
export async function publishToNotebook(taskId: string, notebookId: string): Promise<Result<void, string>>
export async function researchHealth(): Promise<Result<{healthy: boolean}, string>>
```

**Pages:**
- `pmoves/ui/app/dashboard/search/page.tsx`
- `pmoves/ui/app/dashboard/jellyfin/page.tsx`
- `pmoves/ui/app/dashboard/research/page.tsx`

### Commits
- `7566b6a5` - Initial Phase 1 implementation
- `ef737fc8` - API client refinements

---

## Phase 2: Search Interface (Hi-RAG v2) ✅ COMPLETE

### Overview
Connect UI to Hi-RAG v2 for hybrid search across Qdrant (vectors), Neo4j (graph), and Meilisearch (full-text).

### Completed Components
- ✅ `components/search/SearchBar.tsx` - Debounced input, keyboard shortcut (⌘K), search history
- ✅ `components/search/SearchResults.tsx` - Results display with source badges, expandable content
- ✅ `components/search/SearchFilters.tsx` - Filter controls (source type, date range, channel, min score)
- ✅ Updated `app/dashboard/search/page.tsx` to use new components

### Commit
- `363fa408` - feat(search): implement Phase 2 Search Interface components

### API Reference
```
Endpoint: POST http://localhost:8086/hirag/query
Request: { query: string, top_k: number, rerank: boolean }
Response: { results: HiragResult[] }

HiragResult {
  id: string;
  content: string;
  source: string;  // 'youtube', 'notebook', 'pdf', etc.
  score: number;
  metadata: {
    video_id?: string;
    title?: string;
    channel?: string;
    timestamp?: string;
  }
}
```

### Components to Create

**1. SearchBar** (`components/search/SearchBar.tsx`)
```tsx
interface SearchBarProps {
  onSearch: (query: string, filters?: SearchFilters) => void;
  loading?: boolean;
  placeholder?: string;
}

// Features:
- Debounced input (300ms)
- Filter dropdown (content type, date range, source)
- Search history (localStorage)
- Keyboard shortcut (Cmd+K / Ctrl+K)
```

**2. SearchResults** (`components/search/SearchResults.tsx`)
```tsx
interface SearchResultProps {
  results: HiragResult[];
  onExport?: (result: HiragResult) => void;
  onCopy?: (content: string) => void;
}

// Features:
- Results list with relevance scores
- Source attribution badges
- Expandable content preview
- Export to Notebook action
- Copy to clipboard
```

**3. SearchFilters** (`components/search/SearchFilters.tsx`)
```tsx
interface SearchFiltersProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

interface SearchFilters {
  sourceType?: string;
  dateFrom?: string;
  dateTo?: string;
  minScore?: number;
}
```

### Page Structure
```
app/dashboard/search/page.tsx
├── SearchBar (sticky top)
├── SearchFilters (collapsible sidebar)
├── SearchResults (main area)
└── Load More / Pagination
```

---

## Phase 3: Jellyfin Integration

### Overview
Manage media library synchronization and link YouTube videos to Jellyfin items.

### API Reference
```
Base URL: http://localhost:8093

GET /jellyfin/search?term={query}
Response: { items: JellyfinItem[] }

POST /jellyfin/link
Request: { video_id: string, jellyfin_id: string }
Response: { success: boolean }

POST /jellyfin/playback-url
Request: { jellyfin_id: string, timestamp?: number }
Response: { url: string, expires_at: string }

GET /jellyfin/branding
Response: { logo_url: string, theme: {...} }

GET /jellyfin/sync-status
Response: JellyfinSyncStatusInfo {
  videosLinked: number;
  pendingBackfill: number;
  status: string;
  errors: number;
  lastSync?: string;
}

POST /jellyfin/sync
Response: { triggered: true }

POST /jellyfin/backfill
Request: { limit?: number }
Response: { queued: number }
```

### Components to Create

**1. JellyfinMediaBrowser** (`components/jellyfin/JellyfinMediaBrowser.tsx`)
```tsx
interface JellyfinMediaBrowserProps {
  onLink: (videoId: string, jellyfinId: string) => void;
}

// Features:
- Grid view of library items
- Thumbnail previews
- Filter by collection/genre
- Auto-match YouTube videos
- Playback URL generation
```

**2. SyncStatus** (`components/jellyfin/SyncStatus.tsx`)
```tsx
interface SyncStatusProps {
  status: JellyfinSyncStatusInfo;
  onRefresh: () => void;
  onSync: () => void;
  onBackfill: (limit?: number) => void;
}

// Features:
- Real-time status via Supabase
- Progress bars for backfill
- Error list with retry
- Manual sync trigger
```

**3. BackfillControls** (`components/jellyfin/BackfillControls.tsx`)
```tsx
// Features:
- Batch backfill configuration
- Priority settings
- Progress tracking
- Cancel operations
```

### Database Tables (if not exists)
```sql
CREATE TABLE IF NOT EXISTS jellyfin_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  jellyfin_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,  -- 'movie', 'series', 'episode'
  series_name TEXT,
  season_number INT,
  episode_number TEXT,
  youtube_id TEXT REFERENCES videos(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jellyfin_sync_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status TEXT NOT NULL,
  videos_linked INT DEFAULT 0,
  pending_backfill INT DEFAULT 0,
  errors INT DEFAULT 0,
  error_details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE jellyfin_sync_log REPLICA IDENTITY FULL;
```

### Checklist
- [x] Create JellyfinMediaBrowser component
- [x] Create SyncStatus component
- [x] Create BackfillControls component
- [x] Implement real-time sync status (Supabase)
- [x] Add error handling with retry
- [x] Add playback URL generation
- [x] Create database migrations if needed
- [x] Add CORS to Jellyfin bridge service

---

## Phase 4: Deep Research Dashboard

### Overview
Research task management with real-time status updates and result viewing.

### API Reference
```
Base URL: http://localhost:8098

GET /healthz
Response: { healthy: boolean, version?: string }

POST /research/initiate
Request: {
  query: string;
  mode: 'tensorzero' | 'openrouter' | 'local' | 'hybrid';
  notebook_id?: string;
  max_iterations?: number;
  priority?: number;
}
Response: ResearchTask

GET /research/tasks
Query: ?status={status}&limit={limit}&offset={offset}
Response: { tasks: ResearchTask[] }

GET /research/tasks/{id}
Response: ResearchTask

GET /research/tasks/{id}/results
Response: ResearchResult {
  taskId: string;
  summary: string;
  notes: string[];
  sources: Array<{title: string; url: string; snippet?: string}>;
  iterations: number;
  duration: number;
  completedAt: string;
}

POST /research/tasks/{id}/cancel
Response: { cancelled: true }

POST /research/tasks/{id}/publish
Request: { notebook_id: string }
Response: { published: true; note_id?: string }
```

### Components to Create

**1. ResearchTaskList** (`components/research/ResearchTaskList.tsx`)
```tsx
interface ResearchTaskListProps {
  tasks: ResearchTask[];
  selectedId?: string;
  onSelect: (task: ResearchTask) => void;
  onCancel: (taskId: string) => void;
  onRefresh: () => void;
}

// Features:
- Status badges (pending, running, completed, failed, cancelled)
- Filter by status/date
- Real-time updates (poll or NATS)
- Cancel button for running tasks
```

**2. ResearchResults** (`components/research/ResearchResults.tsx`)
```tsx
interface ResearchResultsProps {
  result: ResearchResult;
  onPublish: (notebookId: string) => void;
  onCopy: () => void;
}

// Features:
- Expandable sections (summary, notes, sources)
- Source links with favicon
- Export to Notebook
- Copy to clipboard
- Iteration count display
- Confidence score
```

**3. TaskInitiationForm** (`components/research/TaskInitiationForm.tsx`)
```tsx
interface TaskInitiationFormProps {
  onSubmit: (query: string, options: ResearchOptions) => void;
  loading?: boolean;
}

// Features:
- Multiline query input
- Mode selection (tensorzero, openrouter, local, hybrid)
- Notebook selection dropdown
- Priority slider (1-10)
- Max iterations input
```

### Real-time Updates
```typescript
// Option 1: Polling
setInterval(() => {
  refreshTasks();
}, 5000); // Every 5 seconds

// Option 2: NATS subscription (preferred)
// Subscribe to research task status updates via NATS
// Requires WebSocket connection to NATS or gateway
```

### Checklist
- [ ] Create ResearchTaskList component
- [ ] Create ResearchResults component
- [ ] Create TaskInitiationForm component
- [ ] Implement real-time status updates
- [ ] Add polling fallback
- [ ] Implement cancel functionality
- [ ] Add export to Notebook
- [ ] Add copy to clipboard
- [ ] Add notebook selection dropdown

---

## Phase 5: Enhanced Video Approval

### Overview
Add bulk actions and workflow rules to the existing ingestion queue.

### Existing Files to Modify
- `pmoves/ui/app/dashboard/ingestion-queue/page.tsx`
- `pmoves/ui/components/IngestionQueueTable.tsx`
- `pmoves/ui/components/VideoRow.tsx`

### Components to Create

**1. BulkApprovalActions** (`components/ingestion/BulkApprovalActions.tsx`)
```tsx
interface BulkApprovalActionsProps {
  selectedIds: string[];
  onApprove: (ids: string[], priority?: number) => void;
  onReject: (ids: string[], reason?: string) => void;
  onExport: (ids: string[]) => void;
  onClearSelection: () => void;
}

// Features:
- Select all / deselect all
- Filter selection by source/type
- Bulk approve with priority
- Bulk reject with reason
- Export selected to CSV
```

**2. ApprovalRulesConfig** (`components/ingestion/ApprovalRulesConfig.tsx`)
```tsx
interface ApprovalRule {
  id: string;
  name: string;
  enabled: boolean;
  conditions: {
    sourceType?: string;
    channelContains?: string;
    minDuration?: number;
    maxDuration?: number;
  };
  action: 'auto_approve' | 'auto_reject' | 'flag';
  priority?: number;
}

interface ApprovalRulesConfigProps {
  rules: ApprovalRule[];
  onCreate: (rule: Omit<ApprovalRule, 'id'>) => void;
  onUpdate: (id: string, rule: Partial<ApprovalRule>) => void;
  onDelete: (id: string) => void;
  onTest: (rule: ApprovalRule) => Promise<boolean>;
}

// Features:
- Rule list with enable/disable
- Create/edit rule modal
- Rule conditions builder
- Test rule against pending items
- Execution log
```

### IngestionQueueTable Enhancements
```tsx
// Add to existing:
- Checkbox column for bulk selection
- Approval rule indicator icon
- Related Jellyfin item link (if linked)
- Quick actions dropdown
- Bulk action bar (shows when items selected)
```

### Database Functions
```sql
-- Bulk approve
CREATE OR REPLACE FUNCTION approve_ingestion_bulk(
  ids uuid[],
  priority int DEFAULT 5
) RETURNS TABLE (id uuid, success boolean) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  UPDATE ingestion_queue
  SET status = 'approved', priority = $2
  WHERE id = ANY(ids)
  RETURNING id, (status = 'approved')::boolean;
END;
$$;

-- Bulk reject
CREATE OR REPLACE FUNCTION reject_ingestion_bulk(
  ids uuid[],
  reason text DEFAULT 'Bulk rejected'
) RETURNS TABLE (id uuid, success boolean) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  UPDATE ingestion_queue
  SET status = 'rejected', rejection_reason = $2
  WHERE id = ANY(ids)
  RETURNING id, (status = 'rejected')::boolean;
END;
$$;
```

### Checklist
- [ ] Create BulkApprovalActions component
- [ ] Create ApprovalRulesConfig component
- [ ] Update IngestionQueueTable with checkboxes
- [ ] Update VideoRow with rule indicators
- [ ] Add bulk action bar
- [ ] Add database functions
- [ ] Implement rule testing
- [ ] Add export to CSV
- [ ] Add Jellyfin item links

---

## Phase 6: Integration & Testing

### Overview
Wire up all real-time subscriptions and ensure quality standards.

### Real-time Client Updates

**File:** `pmoves/ui/lib/realtimeClient.ts`

```typescript
// Jellyfin sync status subscription
export function subscribeToJellyfinSync(
  callback: (status: JellyfinSyncStatus) => void
): () => void {
  const channel = supabase
    .channel('jellyfin_sync_changes')
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'jellyfin_sync_log',
      },
      (payload) => callback(payload.new as JellyfinSyncStatus)
    )
    .subscribe();
  return () => channel.unsubscribe();
}

// Research task subscription (via polling or WebSocket)
export function subscribeToResearchTasks(
  callback: (tasks: ResearchTask[]) => void,
  intervalMs: number = 5000
): () => void {
  const interval = setInterval(async () => {
    const result = await listResearchTasks({ limit: 20 });
    if (result.ok) callback(result.data);
  }, intervalMs);
  return () => clearInterval(interval);
}
```

### Testing Requirements

**E2E Tests**
```bash
# Create test files:
pmoves/tests/ui/test_search_flow.py
pmoves/tests/ui/test_jellyfin_sync.py
pmoves/tests/ui/test_research_tasks.py
pmoves/tests/ui/test_bulk_approval.py
```

**Accessibility Audit**
```bash
npm run test:a11y
# Verify:
- Skip links present
- ARIA live regions for dynamic content
- Keyboard navigation works
- Screen reader announcements
```

**Performance Tests**
```bash
npm run test:perf
# Test search with 10K+ results
# Test bulk approval with 100+ items
# Verify pagination performance
```

### Security Checklist
- [ ] All API routes validate JWT from header only
- [ ] No PII in error logs (use `logError()`)
- [ ] Proper HTTP status codes (401, 400, 500)
- [ ] CORS configured for Jellyfin bridge
- [ ] Rate limiting on search endpoint
- [ ] Row Level Security on all Supabase queries

### Documentation Checklist
- [ ] Update API documentation
- [ ] Add component stories (Storybook)
- [ ] Update user guide
- [ ] Add deployment notes

---

## Service Endpoints Reference

### Production Services for UI Integration

| Service | Port | Endpoint | Purpose |
|---------|------|----------|---------|
| **Hi-RAG v2** | 8086 | POST /hirag/query | Hybrid search |
| Hi-RAG v2 GPU | 8087 | POST /hirag/query | GPU-accelerated search |
| **Jellyfin Bridge** | 8093 | GET /jellyfin/* | Media sync |
| **DeepResearch** | 8098 | POST /research/* | Research tasks |
| Supabase | 3010 | /rest/v1/* | PostgREST API |
| TensorZero | 3030 | /v1/chat/completions | LLM gateway |

### Environment Variables
```bash
# UI Configuration
NEXT_PUBLIC_HIRAG_URL=http://localhost:8086
NEXT_PUBLIC_JELLYFIN_URL=http://localhost:8093
NEXT_PUBLIC_RESEARCH_URL=http://localhost:8098
NEXT_PUBLIC_SUPABASE_URL=http://localhost:3010

# For production, use proper hostnames
```

---

## File Structure Overview

```
pmoves/ui/
├── app/dashboard/
│   ├── search/page.tsx           # ✅ Created (Phase 1)
│   ├── jellyfin/page.tsx         # ✅ Created (Phase 1)
│   ├── research/page.tsx         # ✅ Created (Phase 1)
│   ├── ingestion-queue/page.tsx  # UPDATE (Phase 5)
│   └── videos/page.tsx           # UPDATE (Phase 5)
│
├── components/
│   ├── search/
│   │   ├── SearchBar.tsx          # NEW (Phase 2)
│   │   ├── SearchResults.tsx      # NEW (Phase 2)
│   │   └── SearchFilters.tsx      # NEW (Phase 2)
│   ├── jellyfin/
│   │   ├── JellyfinMediaBrowser.tsx  # NEW (Phase 3)
│   │   ├── SyncStatus.tsx            # NEW (Phase 3)
│   │   └── BackfillControls.tsx      # NEW (Phase 3)
│   ├── research/
│   │   ├── ResearchTaskList.tsx   # NEW (Phase 4)
│   │   ├── ResearchResults.tsx    # NEW (Phase 4)
│   │   └── TaskInitiationForm.tsx # NEW (Phase 4)
│   └── ingestion/
│       ├── BulkApprovalActions.tsx  # NEW (Phase 5)
│       └── ApprovalRulesConfig.tsx  # NEW (Phase 5)
│
├── lib/
│   ├── api/
│   │   ├── hirag.ts      # ✅ Created (Phase 1)
│   │   ├── jellyfin.ts    # ✅ Created (Phase 1)
│   │   ├── research.ts    # ✅ Created (Phase 1)
│   │   └── index.ts       # ✅ Updated (Phase 1)
│   └── realtimeClient.ts  # UPDATE (Phase 6)
│
└── docs/
    └── PMOVES.AI PLANS/
        └── UI_INTEGRATION_PHASES.md  # This file
```

---

## Git Workflow

### Feature Branch
```bash
git checkout -b feat/ui-integrations-search-jellyfin-research
# Current branch: feat/ui-integrations-search-jellyfin-research
```

### Commit Pattern
```bash
# Phase 2 commits
git add pmoves/ui/components/search/
git commit -m "feat(search): add SearchBar, SearchResults, SearchFilters components

- Implements debounced search input with keyboard shortcut
- Displays results with source attribution and relevance scores
- Adds filter controls for content type, date range, and minimum score

🤖 Generated with Claude Code"

# Similar pattern for other phases
```

### PR Target
- Target branch: `main`
- Use `gh pr create` with template
- Include Testing section from Phase 6

---

## Additional Resources

### Internal Documentation
- `.claude/context/ui-patterns.md` - UI development patterns
- `.claude/context/services-catalog.md` - Complete service listing
- `.claude/context/nats-subjects.md` - NATS event reference

### External Documentation
- Next.js App Router: https://nextjs.org/docs/app
- Supabase Realtime: https://supabase.com/docs/guides/realtime
- Tailwind CSS: https://tailwindcss.com/docs

---

**Last Updated:** 2025-12-27
**Document Version:** 1.0
**Maintainer:** PMOVES.AI Development Team
