#!/usr/bin/env python3
"""
Ingest consciousness chunks into Hi-RAG v2.

Reads from consciousness-chunks.jsonl and upserts to Qdrant + Meilisearch via Hi-RAG API.
"""

import json
import subprocess
from pathlib import Path


def main():
    # Read chunks from JSONL
    chunks_file = Path("pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/embeddings-ready/consciousness-chunks.jsonl")
    chunks = []

    with open(chunks_file) as f:
        for line in f:
            chunks.append(json.loads(line))

    print(f"Read {len(chunks)} chunks from JSONL")

    # Transform to Hi-RAG format (ensure doc_id is never None)
    items = []
    for chunk in chunks:
        url = chunk.get('url')
        doc_id = url if url else f"consciousness-{chunk['category']}"
        items.append({
            "chunk_id": chunk['id'],
            "doc_id": doc_id,
            "section_id": chunk['category'],
            "text": chunk.get('content', ''),
            "namespace": chunk.get('namespace', 'pmoves.consciousness')
        })

    # Build ingestion script for Docker exec - use regular string formatting
    ingest_script = '''
import requests
import json

items = ''' + repr(items) + '''

print("Ingesting {} items...".format(len(items)))

# Batch ingest in groups of 50
batch_size = 50
total_upserted = 0
total_lexical = 0

for i in range(0, len(items), batch_size):
    batch = items[i:i+batch_size]
    try:
        r = requests.post(
            'http://localhost:8086/hirag/upsert-batch',
            json={
                'items': batch,
                'ensure_collection': True,
                'index_lexical': True
            },
            timeout=60
        )
        if r.ok:
            result = r.json()
            total_upserted += result.get('upserted', 0)
            total_lexical += result.get('lexical_indexed', 0)
            print("  Batch {}: {} vectors, {} lexical".format(i//batch_size + 1, result.get('upserted'), result.get('lexical_indexed')))
        else:
            print("  Batch {} failed: {} {}".format(i//batch_size + 1, r.status_code, r.text[:200]))
    except Exception as e:
        print("  Batch {} error: {}".format(i//batch_size + 1, e))

print("\\nTotal: {} vectors, {} lexical indexed".format(total_upserted, total_lexical))
'''

    # Write to temp file
    temp_script = "C:/temp/ingest_hirag_inner.py"
    Path(temp_script).parent.mkdir(parents=True, exist_ok=True)
    with open(temp_script, 'w', encoding='utf-8') as f:
        f.write(ingest_script)

    print(f"Running ingestion script via Docker...")

    # Copy and execute inside container
    subprocess.run([
        'docker', 'cp', temp_script, 'pmoves-hi-rag-gateway-v2-1:/tmp/ingest.py'
    ], check=True)

    result = subprocess.run([
        'docker', 'exec', 'pmoves-hi-rag-gateway-v2-1',
        'python', '/tmp/ingest.py'
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
