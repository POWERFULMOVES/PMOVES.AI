# cipher-village-pr-5-neo4j-graph

Field brief for **any implementation agent** — implement Phase B PR 5 of the
Cipher Village architecture. Cipher memories become Neo4j graph nodes with
inferred edges, enabling graph-traversal search alongside vector search.

Source architecture: `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` §Phase B PR 5.

## Arguments

- `neo4j_url` (string, default `${NEO4J_URL:-bolt://neo4j:7687}`): Neo4j Bolt URL.
- `neo4j_user` (string, default `${NEO4J_USER:-neo4j}`): Neo4j username.
- `neo4j_password` (string, required from env.shared `NEO4J_PASSWORD`): Neo4j password.
- `edge_inference` (string, default `background`): when to infer edges. Options:
  `none` (no auto-edges), `on_store` (synchronous, slower writes),
  `background` (async job, fast writes — recommended).

## Implementation

### 1. Add neo4j-driver dependency

In `Pmoves-cipher/package.json`, add to `dependencies`:

```json
"neo4j-driver": "^5.27.0"
```

Then `npm install --package-lock-only` to regenerate the lock (this was the
source of the PR #2116 build failure — always regenerate after dep changes).

### 2. Create graph.ts

Create `Pmoves-cipher/src/pmoves/graph.ts`:

```typescript
import neo4j, {Driver, Session} from 'neo4j-driver'

export interface GraphNode {
  id: string                // cipher memory id (nanoid)
  agentId: string
  category: string
  tags: string[]
  contentPreview: string    // first 200 chars (full content stays in Qdrant/MemoryManager)
  ts: string                // ISO timestamp
}

export interface GraphNeighborhood {
  center: GraphNode
  neighbors: Array<{node: GraphNode, relationship: string, depth: number}>
}

class Neo4jGraphClient {
  private driver: Driver

  constructor(url: string, user: string, password: string) {
    this.driver = neo4j.driver(url, neo4j.auth.basic(user, password))
  }

  async ensureConstraints(): Promise<void> {
    // Create uniqueness constraint on Memory.id
    const session = this.driver.session()
    try {
      await session.run('CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE')
      await session.run('CREATE INDEX memory_agent_category IF NOT EXISTS FOR (m:Memory) ON (m.agentId, m.category)')
    } finally {
      await session.close()
    }
  }

  async writeMemory(node: GraphNode): Promise<void> {
    const session = this.driver.session()
    try {
      await session.run(
        `MERGE (m:Memory {id: $id})
         SET m.agentId = $agentId, m.category = $category, m.tags = $tags,
             m.contentPreview = $contentPreview, m.ts = $ts`,
        {id: node.id, agentId: node.agentId, category: node.category,
         tags: node.tags, contentPreview: node.contentPreview, ts: node.ts}
      )
    } finally {
      await session.close()
    }
  }

  async inferEdges(memoryId: string): Promise<number> {
    // Infer SAME_CATEGORY edges between this memory and others with same agentId + category
    const session = this.driver.session()
    try {
      const result = await session.run(
        `MATCH (m:Memory {id: $id}), (other:Memory)
         WHERE m.agentId = other.agentId
           AND m.category = other.category
           AND m.id <> other.id
           AND NOT (m)-[:SAME_CATEGORY]-(other)
         WITH m, other LIMIT 50
         CREATE (m)-[:SAME_CATEGORY {inferred: true, ts: datetime()}]->(other)
         RETURN count(*) as edgeCount`,
        {id: memoryId}
      )
      return result.records[0]?.get('edgeCount').toNumber() ?? 0
    } finally {
      await session.close()
    }
  }

  async expand(memoryId: string, maxDepth: number, agentId: string): Promise<GraphNeighborhood | null> {
    // N-hop traversal, scoped by agentId
    const session = this.driver.session()
    try {
      const result = await session.run(
        `MATCH path = (m:Memory {id: $id})-[*1..$depth]-(other:Memory)
         WHERE m.agentId = $agentId AND other.agentId = $agentId
         WITH m, other, relationships(path) as rels, length(path) as depth
         ORDER BY depth
         LIMIT 20
         RETURN m, collect({node: other, rels: rels, depth: depth}) as neighbors`,
        {id: memoryId, depth: maxDepth, agentId}
      )
      if (result.records.length === 0) return null
      // ...parse into GraphNeighborhood
    } finally {
      await session.close()
    }
  }

  async deleteMemory(memoryId: string): Promise<void> {
    const session = this.driver.session()
    try {
      await session.run('MATCH (m:Memory {id: $id}) DETACH DELETE m', {id: memoryId})
    } finally {
      await session.close()
    }
  }

  async close(): Promise<void> {
    await this.driver.close()
  }
}
```

### 3. Wire into store flow

In `Pmoves-cipher/src/pmoves/mcp-sse.ts`, modify `TOOL_STORE` handler:

After `sidecar.storeVector(...)`, add:
```typescript
const graph = getGraphClient()
if (graph) {
  await graph.writeMemory({
    id: created.id, agentId, category, tags: allTags,
    contentPreview: content.slice(0, 200), ts: new Date().toISOString()
  })
  // Edge inference runs async (background mode) — don't await
  if (edgeInferenceMode === 'on_store') {
    await graph.inferEdges(created.id)
  } else {
    graph.inferEdges(created.id).catch(e => process.stderr.write(`graph edge inference failed: ${e}\n`))
  }
}
```

### 4. Wire into delete flow

In `TOOL_SEARCH` / memory-routes delete: call `graph.deleteMemory(id)` alongside `sidecar.deleteVector(id)`.

### 5. Add expand tool

Add to tools array in mcp-sse.ts:

```typescript
{
  name: 'pmoves_cipher_graph_expand',
  description: 'Given a memory id, return its graph neighborhood (N-hop traversal via Neo4j). Discovers related memories that share categories, tags, or inferred relationships. Use after pmoves_cipher_search to find contextually connected memories the vector search missed.',
  inputSchema: {
    type: 'object',
    properties: {
      memoryId: {type: 'string', description: 'Memory id from a prior search result.'},
      agentId: {type: 'string'},
      maxDepth: {type: 'number', description: 'Max traversal depth (1-3). Default 2.', default: 2},
    },
    required: ['memoryId', 'agentId'],
  },
}
```

Handler calls `graph.expand(memoryId, maxDepth, agentId)`.

### 6. Fail-open design

If Neo4j is unreachable at startup, `getGraphClient()` returns `null`. All graph
operations become no-ops. Cipher still works via Qdrant + MemoryManager only.
Log a warning at boot but don't crash.

## Related

- `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` §Phase B PR 5 — canonical spec
- `Pmoves-cipher/src/pmoves/embedding.ts` — Qdrant sidecar pattern to mirror
- `Pmoves-cipher/src/pmoves/mcp-sse.ts` — TOOL_STORE handler to extend
- Neo4j running on SPARK at `:7687` (verified reachable from cipher-api)

## Notes

- Neo4j driver is ~2MB — adds to image size but is the official driver.
- `MERGE` (not `CREATE`) prevents duplicates on re-store of same memory id.
- Edge inference is O(N) per store where N = existing memories in same agent+category. `LIMIT 50` caps it. Background mode prevents write latency.
- The `contentPreview` is intentionally short (200 chars) — Neo4j isn't the content store, it's the graph layer. Full content lives in Qdrant payload + MemoryManager.
- `DETACH DELETE` removes the node AND its relationships — important for clean deletes.
- Schema constraint `memory_id_unique` ensures no duplicate nodes.
- Test: store 3 memories with same category for same agent, then expand → should show SAME_CATEGORY edges.

## Verification

```bash
# 1. Neo4j reachable (already verified on SPARK)
docker exec pmoves-cipher-api node -e "const net=require('net');const s=net.createConnection({host:'neo4j',port:7687},()=>{console.log('✓');s.end();});setTimeout(()=>process.exit(0),1500);"

# 2. Store 3 memories, same category, same agent
#    pmoves_cipher_store(content="decision A", category="decision", agentId="test-graph")
#    pmoves_cipher_store(content="decision B", category="decision", agentId="test-graph")
#    pmoves_cipher_store(content="decision C", category="decision", agentId="test-graph")

# 3. Graph expand on memory A:
#    pmoves_cipher_graph_expand(memoryId="<A-id>", agentId="test-graph")
#    → should return B and C as SAME_CATEGORY neighbors

# 4. Neo4j Browser verification (port 7474):
#    MATCH (m:Memory {agentId: "test-graph"}) RETURN m
```
