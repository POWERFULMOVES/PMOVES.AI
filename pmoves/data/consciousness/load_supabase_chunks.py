#!/usr/bin/env python3
"""Load consciousness chunks into Supabase pmoves_core.consciousness_theories table."""

import json
import subprocess
import tempfile
from pathlib import Path


def escape_sql(value: str) -> str:
    """Escape single quotes for SQL."""
    return value.replace("'", "''")


def main():
    # Read chunks from JSONL
    chunks_file = Path("pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/embeddings-ready/consciousness-chunks.jsonl")
    chunks = []

    with open(chunks_file) as f:
        for line in f:
            chunks.append(json.loads(line))

    print(f"Read {len(chunks)} chunks from JSONL")

    # Build SQL INSERT statements
    sql_lines = []
    for chunk in chunks:
        chunk_id = escape_sql(chunk['id'])
        title = escape_sql(chunk['title'])
        url = chunk.get('url')
        if url is None:
            url_val = 'NULL'
        else:
            url_val = f"'{escape_sql(url)}'"
        category = escape_sql(chunk['category'])
        content = escape_sql(chunk.get('content', ''))[:5000]  # Limit content length
        namespace = escape_sql(chunk.get('namespace', 'pmoves.consciousness'))

        sql = (f"INSERT INTO pmoves_core.consciousness_theories "
               f"(id, title, url, category, content, namespace) VALUES "
               f"('{chunk_id}', '{title}', {url_val}, '{category}', '{content}', '{namespace}') "
               f"ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, url=EXCLUDED.url, "
               f"category=EXCLUDED.category, content=EXCLUDED.content, namespace=EXCLUDED.namespace;")
        sql_lines.append(sql)

    # Write to temp file (cross-platform)
    temp_dir = tempfile.gettempdir()
    temp_sql = Path(temp_dir) / "consciousness_seed.sql"
    temp_sql.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_sql, 'w') as f:
        f.write('\n'.join(sql_lines))

    print(f"Wrote {len(sql_lines)} SQL statements to {temp_sql}")

    # Load via Docker
    result = subprocess.run([
        'docker', 'exec', '-i', 'pmoves-supabase-db-1',
        'bash', '-c',
        'PGPASSWORD=zode0dl7/JgAaNoVqjzHQ0S5Iq1vi7Tt psql -U postgres -d pmoves -h localhost'
    ], stdin=open(temp_sql), capture_output=True, text=True)

    # Check return code
    result.check_returncode()

    print(f"Exit code: {result.returncode}")
    if result.stdout:
        print(f"STDOUT: {result.stdout[:500]}")
    if result.stderr:
        print(f"STDERR: {result.stderr[:500]}")

    # Verify
    verify = subprocess.run([
        'docker', 'exec', 'pmoves-supabase-db-1',
        'bash', '-c',
        'PGPASSWORD=zode0dl7/JgAaNoVqjzHQ0S5Iq1vi7Tt psql -U postgres -d pmoves -h localhost -t -c "SELECT COUNT(*) FROM pmoves_core.consciousness_theories"'
    ], capture_output=True, text=True)

    # Check return code
    verify.check_returncode()
    print(f"\nVerified row count: {verify.stdout.strip()}")


if __name__ == "__main__":
    main()
