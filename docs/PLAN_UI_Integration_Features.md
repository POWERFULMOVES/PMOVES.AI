# PMOVES UI Integration Features Plan

**Status:** Planning
**Created:** 2025-12-27
**Feature Branch:** `feat/ui-integrations-search-jellyfin-research`
**Related Submodules:** PMOVES-Open-Notebook, PMOVES-ToKenism-Multi

---

## Overview

Implement four major UI integration features to reflect the full PMOVES ecosystem in the PMOVES UI.

### Features

| Feature | Description | Priority | Related Services |
|---------|-------------|----------|------------------|
| **Search Interface** | Connect to Hi-RAG v2 for hybrid search | High | Hi-RAG Gateway, Qdrant, Neo4j, Meilisearch |
| **Jellyfin Integration** | Media sync and backfill controls | High | Jellyfin Bridge, Open Notebook |
| **Deep Research Dashboard** | Research task management | Medium | DeepResearch, Open Notebook |
| **Enhanced Video Approval** | Bulk actions and workflow rules | Medium | Supabase, PMOVES.YT |

---

## Open Notebook Integration

### API Endpoint
- **Open Notebook** (`http://localhost:5055`):
  - `/api/sources` - List/manage knowledge sources
  - `/api/models` - Model configuration
  - `/api/search` - Search within notebook
  - `/api/notes` - CRUD for notes

### Integration Points

| Feature | Open Notebook API | Purpose |
|---------|-------------------|---------|
| **Search Results** | `POST /api/search` | Export search results to notebook |
| **Research Publishing** | `POST /api/sources/{id}/notes` | Auto-publish research results |
| **Video Transcripts** | Sync from `youtube_transcripts` table | Browse transcripts in notebook |
| **Media Analysis** | Link to MinIO media | Playback from notebook links |

---

## Architecture

### UI Development Patterns (from `.claude/context/ui-patterns.md`)

**Must Follow:**
- **Error Handling**: `ErrorBoundary` wrapper, `logError()` for production
- **Authentication**: JWT from token only, `ownerFromJwt()` pattern
- **Accessibility**: Skip links, ARIA live regions, `tabIndex={-1}`
- **Tailwind JIT**: Static class lookup objects (no interpolation)
- **API Responses**: `{ok, error}` or `{items, error}` shapes
- **HTTP Codes**: 401 (auth), 400 (bad request), 500 (server)

---

## Feature 1: Search Interface (Hi-RAG Integration)

### API Endpoint
- **Hi-RAG v2**: `POST http://localhost:8086/hirag/query`
- **Request**: `{query: string, top_k: number, rerank: boolean}`
- **Response**: Results from Qdrant (vectors) + Neo4j (graph) + Meilisearch (full-text)

### Components

| Component | Path | Description |
|-----------|------|-------------|
| SearchBar | `components/search/SearchBar.tsx` | Search input with filters, keyboard shortcut |
| SearchResults | `components/search/SearchResults.tsx` | Results display with source attribution |
| SearchFilters | `components/search/SearchFilters.tsx` | Content type, date range filters |
| Search Page | `app/dashboard/search/page.tsx` | Main search page |

### API Client

```typescript
// lib/api/hirag.ts
export async function hiragQuery(
  query: string,
  options?: { top_k?: number; rerank?: boolean; filters?: SearchFilters }
): Promise<{ items: SearchResult[]; error?: string }>
```

---

## Feature 2: Jellyfin Integration

### API Endpoints
- **Jellyfin Bridge** (`http://localhost:8093`):
  - `GET /jellyfin/search` - Search library
  - `POST /jellyfin/link` - Link video to Jellyfin item
  - `POST /jellyfin/playback-url` - Generate playback URL

### Components

| Component | Path | Description |
|-----------|------|-------------|
| JellyfinMediaBrowser | `components/jellyfin/JellyfinMediaBrowser.tsx` | Grid view of library |
| SyncStatus | `components/jellyfin/SyncStatus.tsx` | Sync status dashboard |
| BackfillControls | `components/jellyfin/BackfillControls.tsx` | Backfill operations |
| Jellyfin Page | `app/dashboard/jellyfin/page.tsx` | Main Jellyfin page |

---

## Feature 3: Deep Research Dashboard

### API Endpoints
- **DeepResearch** (`http://localhost:8098`):
  - `/healthz` - Service health
  - NATS: `research.deepresearch.request.v1` / `research.deepresearch.result.v1`

### Components

| Component | Path | Description |
|-----------|------|-------------|
| ResearchTaskList | `components/research/ResearchTaskList.tsx` | Task list with status |
| ResearchResults | `components/research/ResearchResults.tsx` | Result display |
| TaskInitiationForm | `components/research/TaskInitiationForm.tsx` | New task form |
| Research Page | `app/dashboard/research/page.tsx` | Main research page |

---

## Feature 4: Enhanced Video Approval

### Existing to Enhance
- `app/dashboard/ingestion-queue/page.tsx`
- `components/IngestionQueueTable.tsx`
- `components/VideoRow.tsx`

### New Components

| Component | Path | Description |
|-----------|------|-------------|
| BulkApprovalActions | `components/ingestion/BulkApprovalActions.tsx` | Bulk approve/reject |
| ApprovalRulesConfig | `components/ingestion/ApprovalRulesConfig.tsx` | Auto-approval rules |

---

## Implementation Phases

### Phase 1: Foundation
- [ ] Update navigation with new routes
- [ ] Create API client functions (`lib/api/`)
- [ ] Set up error boundaries
- [ ] Implement JWT auth

### Phase 2: Search Interface
- [ ] SearchBar component
- [ ] SearchResults component
- [ ] Hi-RAG API integration
- [ ] Export to Open Notebook action

### Phase 3: Jellyfin Integration
- [ ] JellyfinMediaBrowser component
- [ ] SyncStatus component
- [ ] Jellyfin bridge API calls
- [ ] Link to Open Notebook sources

### Phase 4: Deep Research Dashboard
- [ ] ResearchTaskList component
- [ ] ResearchResults component
- [ ] TaskInitiationForm component
- [ ] Auto-publish to Open Notebook

### Phase 5: Enhanced Approval
- [ ] BulkApprovalActions component
- [ ] ApprovalRulesConfig component
- [ ] Update IngestionQueueTable
- [ ] Database bulk functions
