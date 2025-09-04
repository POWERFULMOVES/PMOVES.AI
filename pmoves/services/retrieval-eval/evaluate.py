import os, sys, json, math, csv
import requests

HIRAG_URL = os.environ.get('HIRAG_URL','http://hi-rag-gateway-v2:8086')

def dcg(scores):
    return sum((s / math.log2(i+2)) for i, s in enumerate(scores))

def ndcg_at_k(rels, k):
    gains = [1.0 if r else 0.0 for r in rels[:k]]
    idcg = dcg(sorted(gains, reverse=True))
    return (dcg(gains) / idcg) if idcg > 0 else 0.0

def mrr_at_k(rels, k):
    for i, r in enumerate(rels[:k]):
        if r:
            return 1.0/(i+1)
    return 0.0

def main():
    if len(sys.argv) < 2:
        print('Usage: evaluate.py /path/queries.jsonl [k=10] [csv]')
        sys.exit(2)
    path = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    out_csv = (len(sys.argv) > 3 and sys.argv[3].lower() == 'csv')
    total, mrr_sum, ndcg_sum = 0, 0.0, 0.0
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            q = json.loads(line)
            query = q['query']
            ns = q.get('namespace','pmoves')
            relevant = set(q.get('relevant', [])) or set()
            resp = requests.post(f"{HIRAG_URL}/hirag/query", headers={'content-type':'application/json'}, data=json.dumps({'query': query, 'namespace': ns, 'k': k}))
            hits = (resp.json() or {}).get('hits', [])
            rels = []
            for h in hits:
                cid = h.get('chunk_id') or (h.get('payload') or {}).get('chunk_id')
                rels.append(1 if (cid and cid in relevant) else 0)
            mrr = mrr_at_k(rels, k)
            ndcg = ndcg_at_k(rels, k)
            mrr_sum += mrr
            ndcg_sum += ndcg
            total += 1
            rows.append({'query': query, 'namespace': ns, 'k': k, 'mrr': mrr, 'ndcg': ndcg})
    if out_csv:
        w = csv.DictWriter(sys.stdout, fieldnames=['query','namespace','k','mrr','ndcg'])
        w.writeheader(); w.writerows(rows)
    else:
        print(json.dumps({'count': total, 'MRR@k': (mrr_sum/total if total else 0.0), 'NDCG@k': (ndcg_sum/total if total else 0.0), 'k': k}, indent=2))

if __name__ == '__main__':
    main()
