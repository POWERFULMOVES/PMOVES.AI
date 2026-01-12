import os, sys, json
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

QDRANT_URL = os.environ.get('QDRANT_URL','http://qdrant:6333')
COLL = os.environ.get('QDRANT_COLLECTION','pmoves_chunks')

def main():
    if len(sys.argv) < 2:
        print('Usage: export_jsonl.py /path/output.jsonl [namespace] [limit]')
        sys.exit(2)
    out_path = sys.argv[1]
    ns = sys.argv[2] if len(sys.argv) > 2 else None
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    qc = QdrantClient(url=QDRANT_URL, timeout=30.0)
    must = []
    if ns:
        must.append(FieldCondition(key='namespace', match=MatchValue(value=ns)))
    with open(out_path, 'w', encoding='utf-8') as w:
        offset = None
        total = 0
        while True:
            points, offset = qc.scroll(collection_name=COLL, scroll_filter=Filter(must=must) if must else None, with_payload=True, with_vectors=False, limit=min(256, lim-total), offset=offset)
            if not points:
                break
            for p in points:
                d = p.payload
                w.write(json.dumps({
                    'doc_id': d.get('doc_id'),
                    'section_id': d.get('section_id'),
                    'chunk_id': d.get('chunk_id'),
                    'namespace': d.get('namespace'),
                    'text': d.get('text','')
                }, ensure_ascii=False) + '\n')
                total += 1
                if total >= lim:
                    break
            if total >= lim or offset is None:
                break
    print(f'Exported {total} docs to {out_path}')

if __name__ == '__main__':
    main()

