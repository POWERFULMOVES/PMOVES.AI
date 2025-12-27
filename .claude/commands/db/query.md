# Database Query

Execute safe read-only queries against PMOVES Supabase database.

## Usage

```
/db:query <sql_or_table>
```

## Arguments

- `sql_or_table`: SQL SELECT query or table name to inspect

## What This Command Does

1. **Table Inspection:**
   ```bash
   # List all tables
   curl -X GET "${SUPABASE_URL}/rest/v1/" \
     -H "apikey: ${SUPABASE_SERVICE_KEY}" \
     -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}"
   ```

2. **Query Execution (via PostgREST):**
   ```bash
   # Simple table query
   curl -X GET "${SUPABASE_URL}/rest/v1/<table>?select=*&limit=10" \
     -H "apikey: ${SUPABASE_SERVICE_KEY}" \
     -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}"
   ```

3. **SQL Query (via RPC):**
   ```bash
   # Custom SQL via database function
   curl -X POST "${SUPABASE_URL}/rest/v1/rpc/execute_sql" \
     -H "apikey: ${SUPABASE_SERVICE_KEY}" \
     -H "Content-Type: application/json" \
     -d '{"query": "SELECT ..."}'
   ```

## Safety Rules

### ALLOWED Operations
- `SELECT` queries (read-only)
- `EXPLAIN` for query analysis
- Table/column inspection
- Index listing
- Row counts

### BLOCKED Operations
- `INSERT`, `UPDATE`, `DELETE`
- `DROP`, `TRUNCATE`, `ALTER`
- `CREATE`, `GRANT`, `REVOKE`
- Any DDL operations

## PMOVES Database Schema

### Core Tables (pmoves_core schema)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `content_items` | Ingested content metadata | id, source, type, status |
| `transcripts` | Video/audio transcripts | content_id, text, segments |
| `embeddings` | Vector embeddings | content_id, vector, model |
| `chunks` | Document chunks for RAG | doc_id, text, metadata |

### Archon Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `sources` | Knowledge sources | id, url, status, crawl_config |
| `documents` | Processed documents | id, source_id, embedding |
| `code_examples` | Extracted code snippets | id, language, summary |

### Media Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `videos` | YouTube video metadata | id, youtube_id, title |
| `frames` | Video frame analysis | video_id, timestamp, objects |
| `audio_segments` | Audio analysis results | video_id, emotion, speaker |

## Output Format

```markdown
## Query Results

### Query
\`\`\`sql
<executed_query>
\`\`\`

### Results
| Column1 | Column2 | ... |
|---------|---------|-----|
| value1  | value2  | ... |

### Statistics
- **Rows Returned:** X
- **Execution Time:** Yms
```

## Example

```bash
# List tables
/db:query tables

# Query specific table
/db:query content_items

# Custom SELECT
/db:query "SELECT id, title, status FROM content_items WHERE status = 'processed' LIMIT 5"

# Count rows
/db:query "SELECT COUNT(*) FROM chunks"

# Join query
/db:query "SELECT c.title, COUNT(ch.id) as chunk_count FROM content_items c JOIN chunks ch ON c.id = ch.content_id GROUP BY c.id LIMIT 10"
```

## Environment Variables

Required:
- `SUPABASE_URL` - Supabase project URL (e.g., `http://localhost:3010`)
- `SUPABASE_SERVICE_KEY` - Service role key (full access)

## Notes

- All queries are read-only for safety
- Use `/db:migrate` for schema changes
- Large result sets are automatically limited
- Sensitive columns (passwords, keys) are redacted in output
- For write operations, use Supabase dashboard or direct psql
