# DARKXSIDE Playlist Analysis

**Crawl Date:** 2026-07-28
**Playlist:** `PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8` (DARKXSIDE AI Playlist)
**Total Items:** 2064 (34 private/deleted excluded)
**Unique Videos Stored:** 2028
**Crawl Method:** YouTube Data API v3 via OAuth refresh token (IP-agnostic)

## Content Distribution

### By Channel (Top 20)

| Channel | Videos | Avg Views | Latest |
|---------|--------|-----------|--------|
| Fahd Mirza | 107 | 25K | 2026-07-27 |
| Discover AI | 75 | 6K | 2026-07-17 |
| AICodeKing | 43 | 24K | 2026-06-04 |
| Richard Aragon | 40 | 2K | 2026-06-30 |
| Keith D | 36 | 95K | 2026-07-25 |
| Cole Medin | 33 | 55K | 2026-07-02 |
| Bijan Bowen | 31 | 36K | 2026-06-03 |
| AI Search | 27 | 148K | 2026-06-01 |
| Prompt Engineering | 25 | 31K | 2026-07-03 |
| AI News & Strategy Daily | 24 | 65K | 2026-02-19 |
| IndyDevDan | 23 | 36K | 2026-07-13 |
| Coin Bureau | 23 | 95K | 2026-05-21 |
| Aitrepreneur | 22 | 54K | 2026-06-13 |
| Wes Roth | 21 | 86K | 2026-07-08 |
| Sabine Hossenfelder | 21 | 369K | 2026-05-07 |
| David Ondrej | 20 | 98K | 2026-07-15 |
| David Shapiro | 19 | 40K | 2026-04-02 |
| Michael Levin's Academic Content | 18 | 10K | 2026-06-09 |
| Louis Rossmann | 18 | 415K | 2026-07-12 |
| WorldofAI | 17 | 18K | 2026-06-04 |

### By Duration

| Bucket | Count | % |
|--------|-------|---|
| Medium (5-20 min) | 1127 | 56% |
| Long (20-60 min) | 704 | 35% |
| Very Long (1hr+) | 135 | 7% |
| Short (<5 min) | 59 | 3% |

### By Content Type (keyword-classified)

| Type | Count | Avg Views |
|------|-------|-----------|
| Other | 1659 | 369K |
| Tutorial | 239 | 178K |
| Analysis | 51 | 230K |
| News | 27 | 89K |
| Course | 19 | 1.4M |
| Music | 13 | 708K |
| Documentary | 12 | 755K |
| Podcast | 8 | 323K |

### By Topic Cluster (keyword overlap)

| Cluster | Videos Matching |
|---------|----------------|
| AI/ML | 1815 (89%) |
| Media/Creative | 1667 (82%) |
| Energy | 1483 (73%) |
| Dev/Tools | 1129 (56%) |
| Business | 523 (26%) |
| Community | 515 (25%) |
| Crypto/Web3 | 262 (13%) |

## Date Range

- **Earliest:** 2023-08-11
- **Latest:** 2026-07-28
- **Span:** ~3 years of accumulated content

## Top 10 Most Viewed

1. Gorillaz - The Mountain, The Moon Cave and The Sad God (16.5M views)
2. Harvard CS50 - Full Computer Science University Course (13.8M views)
3. Atlantis, Thoth, the Emerald Tablet & the Secret to Immortality (11.9M views)
4. Can you really reach anyone in 6 steps? - Veritasium (10.9M views)
5. J. Cole - The Fall-Off is Inevitable (8.5M views)
6. Jetson ONE - Let the Jetson Air Games begin! (7.3M views)
7. Afroman Trial was Crazy - penguinz0 (6.8M views)
8. Newly Discovered PRIMITIVE WATER FILTER! - Clay Hayes (6.2M views)
9. This ROCKET ENGINE WASN'T DESIGNED BY HUMANS - Integza (6.2M views)
10. Make your own AIR CONDITIONER at home - The Liberty Engine Project (5.5M views)

## Processing Priorities

### Tier 1: AI/Dev Tutorials & Courses (immediate value)
- Fahd Mirza, AICodeKing, Cole Medin, IndyDevDan — AI agent building, MCP, RAG tutorials
- Harvard CS50 AI course, programming course reviews
- David Shapiro — agent philosophy and architecture

### Tier 2: Energy & Community (Fordham Hill relevance)
- Solar power, battery technology, off-grid systems
- Community mesh, cooperatives, cost-saving DIY
- Louis Rossmann — right-to-repair, consumer advocacy

### Tier 3: Research & Analysis (knowledge base enrichment)
- Sabine Hossenfelder — physics/science analysis
- Kurzgesagt — science communication
- 3Blue1Brown — mathematical visualization
- Veritasium — science experiments

### Tier 4: Creative & Cultural (persona grounding)
- Gorillaz, J. Cole — music/media references
- Documentary content — historical/cultural context
- Podcasts — long-form discussions

## Storage

- **Supabase:** `pmoves_core.youtube_videos` (2028 rows, indexed by playlist/published/downloads)
- **JSONL Export:** `pmoves/data/yt-playlists/darkxside_ai_playlist.jsonl` (4.4MB)
- **Crawl Script:** `pmoves/tools/yt_playlist_crawl.py`
- **Make Target:** `make -C pmoves yt-playlist-crawl`

## Next Steps

1. **Selective Download:** Process Tier 1 videos (AI/dev tutorials) through transcribe-and-fetch for full transcription + indexing
2. **HuggingFace Dataset:** Structure as HF dataset for agent fine-tuning and retrieval
3. **SupaSearch Integration:** Wire crawled metadata into Hi-RAG for searchable knowledge base
4. **Persona Grounding:** Map video topics to PMOVES persona resonance domains
5. **Website Enrichment:** Surface curated content on Fordham Hill tenant page
6. **Multi-platform:** Extend crawl to other platforms (yt-dlp supports 1000+ sites)
