/**
 * Ingest Pinokio documentation into Hi-RAG via Extract-Worker.
 * Reads PINOKIO.md (6500+ lines), chunks hierarchically, and indexes
 * into Qdrant (vectors) + Meilisearch (full-text).
 */
module.exports = {
  run: [
    {
      method: "log",
      params: {
        raw: true,
        text: "\n═══════════════════════════════════════════════════\n  Ingesting Pinokio Docs into Hi-RAG\n═══════════════════════════════════════════════════\n"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: ["py -3 tools/ingest_pinokio_docs.py"]
      }
    },
    {
      method: "notify",
      params: {
        html: "Pinokio docs ingested into Hi-RAG. Query with: POST /hirag/query {\"query\": \"pinokio ...\"}",
        type: "success"
      }
    }
  ]
}
