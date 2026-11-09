# cipher-village-pr-6-hirag-bridge

Field brief for **any implementation agent** — implement Phase B PR 6 of the
Cipher Village architecture. Cipher gains a hybrid_search tool that proxies
Hi-RAG v2, enabling cross-collection retrieval (KB + cipher memory) in one call.

Source architecture: `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` §Phase B PR 6.
Pattern (i): cipher calls HiRAG as a service (cipher stays focused on memory;
HiRAG owns retrieval).

## Arguments

- `hirag_url` (string, default `${HIRAG_URL:-http://hi-rag-gateway-v2:8086}`):
  Hi-RAG v2 CPU endpoint.
- `hirag_gpu_url` (string, default `${HIRAG_GPU_URL:-http://hi-rag-gateway-v2-gpu:8087}`):
  Hi-RAG v2 GPU endpoint (for rerank). Optional — falls back to CPU.
- `default_collections` (string[], default `["pmoves_chunks_qwen3"]`):
  HiRAG collections to search (KB collections). Cipher's own collection
  (`pmoves_cipher_memory`) is always included automatically.

## Implementation

### 1. Create hirag-client.ts

Create `Pmoves-cipher/src/pmoves/hirag-client.ts`:

```typescript
export interface HiragQueryParams {
  query: string
  topK?: number              // default 10
  rerank?: boolean           // default true (uses GPU if available)
  collections?: string[]     // HiRAG collections to search (cipher adds its own)
}

export interface HiragResult {
  content: string
  score: number
  collection: string
  metadata?: Record<string, unknown>
}

class HiragClient {
  private cpuUrl: string
  private gpuUrl: string | null
  private useGpu: boolean

  constructor(cpuUrl: string, gpuUrl?: string) {
    this.cpuUrl = cpuUrl
    this.gpuUrl = gpuUrl ?? null
    this.useGpu = !!gpuUrl
  }

  async query(params: HiragQueryParams): Promise<{cpu: HiragResult[], cipher: HiragResult[]}> {
    const {query, topK = 10, rerank = true, collections = []} = params

    // 1. Query HiRAG for KB collections
    //    HiRAG POST /hirag/query expects: {"query": "...", "top_k": N, "rerank": bool}
    //    Returns: {"results": [{content, score, metadata}]}
    //    HiRAG searches its configured Qdrant collection (pmoves_chunks_qwen3 by default).
    //    We can't pass collections[] to HiRAG — it searches whatever it's configured for.
    //    So this is a single KB query + a separate cipher query, fused client-side.
    const cpuResults = await this.queryHirag(query, topK, rerank)

    // 2. Query cipher's own Qdrant collection via the embedding sidecar
    //    (cipher already has this via getEmbeddingSidecar().search())
    //    The calling tool handler does this part (it has access to the sidecar).

    return {cpu: cpuResults, cipher: []}  // cipher results filled by caller
  }

  private async queryHirag(query: string, topK: number, rerank: boolean): Promise<HiragResult[]> {
    const url = this.useGpu && rerank ? this.gpuUrl! : this.cpuUrl
    try {
      const resp = await fetch(`${url}/hirag/query`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query, top_k: topK, rerank}),
        signal: AbortSignal.timeout(15000),
      })
      if (!resp.ok) {
        process.stderr.write(`pmoves-hirag: HiRAG returned ${resp.status}\n`)
        return []
      }
      const data = await resp.json() as {results: Array<{content: string, score: number, metadata?: Record<string, unknown>}>}
      return (data.results ?? []).map(r => ({
        content: r.content,
        score: r.score,
        collection: 'pmoves_chunks_qwen3',
        metadata: r.metadata,
      }))
    } catch (error) {
      process.stderr.write(`pmoves-hirag: query failed — ${error}\n`)
      return []
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.cpuUrl}/healthz`, {signal: AbortSignal.timeout(3000)})
      return resp.ok
    } catch {
      return false
    }
  }
}
```

### 2. Add hybrid_search tool

In `Pmoves-cipher/src/pmoves/mcp-sse.ts`, add to tools array:

```typescript
{
  name: 'pmoves_cipher_hybrid_search',
  description: 'Hybrid search across both cipher memory (this agent\'s stored context) and the PMOVES knowledge base (Hi-RAG v2). Fuses results from Qdrant cipher collection + HiRAG\'s KB collection. Use this when you need both your own past notes AND project documentation in one query. Rerank uses GPU if available.',
  inputSchema: {
    type: 'object',
    properties: {
      query: {type: 'string', description: 'Natural language search query.'},
      agentId: {type: 'string', description: 'Agent identifier (scopes cipher memory search).'},
      topK: {type: 'number', description: 'Results per source. Default 5 (10 total).', default: 5},
      rerank: {type: 'boolean', description: 'Use cross-encoder rerank (GPU if available). Default true.', default: true},
    },
    required: ['query', 'agentId'],
  },
}
```

### 3. Handler implementation

```typescript
if (name === 'pmoves_cipher_hybrid_search') {
  const {query, agentId, topK = 5, rerank = true} = args as {
    query: string; agentId: string; topK?: number; rerank?: boolean
  }

  // Parallel: HiRAG KB search + cipher memory search
  const hirag = getHiragClient()
  const sidecar = getEmbeddingSidecar()
  const queryEmbedding = await sidecar.embed(query)

  const [hiragResults, cipherResults] = await Promise.all([
    hirag ? hirag.query({query, topK, rerank}) : Promise.resolve({cpu: [], cipher: []}),
    (async () => {
      if (!queryEmbedding) return []
      const hits = await sidecar.search(queryEmbedding, query, topK, undefined, agentId)
      return Promise.all(hits.map(async h => {
        try {
          const m = await memoryManager.get(h.id)
          return {content: m.content, score: h.score, collection: 'cipher_memory', metadata: {agentId, category: m.metadata?.category, id: m.id}}
        } catch { return null }
      })).then(rs => rs.filter((r): r is NonNullable<typeof r> => r !== null))
    })(),
  ])

  const fused = [
    ...hiragResults.cpu.map(r => ({...r, source: 'kb'})),
    ...cipherResults.map(r => ({...r, source: 'cipher_memory'})),
  ].sort((a, b) => b.score - a.score)

  nats.emitSearched(query, fused.length, 'hybrid')
  return {content: [{type: 'text', text: JSON.stringify({results: fused, sources: {kb: hiragResults.cpu.length, cipher: cipherResults.length}})}]}
}
```

### 4. Fail-open design

- If HiRAG unreachable: return only cipher results (with a `warnings: ["hirag unreachable"]` field).
- If cipher Qdrant unreachable: return only HiRAG results.
- If both unreachable: return empty results with error explanation.

## Related

- `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` §Phase B PR 6 — canonical spec
- `Pmoves-cipher/src/pmoves/embedding.ts` — Qdrant sidecar (cipher half of the hybrid)
- `.claude/CATALOG.md` Hi-RAG Gateway v2 entry — `:8086` CPU, `:8087` GPU
- `pmoves/services/hi-rag-gateway-v2/` — HiRAG source (for POST /hirag/query contract)

## Notes

- HiRAG POST /hirag/query contract: `{"query": "...", "top_k": N, "rerank": bool}` → `{"results": [{content, score, metadata}]}`. Verified at `pmoves/services/hi-rag-gateway-v2/routes/query.py`.
- HiRAG searches whatever Qdrant collection IT is configured for (`pmoves_chunks_qwen3` by default). We can't pass a `collections[]` param — HiRAG doesn't support multi-collection search yet. So the fusion is client-side: cipher queries its own collection via the sidecar, HiRAG queries the KB, we merge.
- Score scales may differ between HiRAG (cosine + rerank, 0-1) and cipher Qdrant (RRF fusion, 0-1). Both are 0-1 ascending; sort by score descending. Don't try to normalize — just sort.
- The `source` field in each result tells the caller where it came from (`kb` vs `cipher_memory`).
- GPU rerank (port 8087) is optional — if `HIRAG_GPU_URL` is unset or unreachable, falls back to CPU (port 8086) without rerank.
- Parallel `Promise.all` ensures latency = max(hirag, cipher) not sum.
- Test with a query that should hit both sources: e.g. "how does cipher store agent memories" → KB has docs, cipher has the agent's own notes.

## Verification

```bash
# 1. HiRAG reachable (already verified on SPARK — :8086 returns 200)
docker exec pmoves-cipher-api node -e "const net=require('net');const s=net.createConnection({host:'hi-rag-gateway-v2',port:8086},()=>{console.log('✓');s.end();});setTimeout(()=>process.exit(0),1500);"

# 2. Store a cipher memory first:
#    pmoves_cipher_store(content="cipher uses Qdrant for vector storage", category="architecture", agentId="test-hybrid")

# 3. Hybrid search:
#    pmoves_cipher_hybrid_search(query="how does cipher store memories", agentId="test-hybrid", topK=3)
#    → should return BOTH the cipher memory AND KB docs about cipher architecture

# 4. Verify fail-open: stop HiRAG, retry → should return only cipher results with warning
