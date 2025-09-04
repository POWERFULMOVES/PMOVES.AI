
import os, json, time, math, random, requests
import numpy as np
from tabulate import tabulate

GATEWAY = os.environ.get("HIRAG_URL","http://localhost:8087")
DATA = os.environ.get("EVAL_DATA","./datasets/queries.jsonl")
K = int(os.environ.get("EVAL_K","10"))

def load_data(path):
    items = []
    with open(path,"r",encoding="utf-8") as f:
        for line in f:
            items.append(json.loads(line))
    return items

def recall_at_k(pred_ids, gold_ids, k):
    pred = pred_ids[:k]
    gold = set(gold_ids)
    return sum(1 for p in pred if p in gold) / max(1, len(gold))

def ndcg_at_k(pred_ids, gold_ids, k):
    idcg = sum(1.0 / math.log2(i+2) for i in range(min(len(gold_ids), k)))
    dcg = 0.0
    for i, pid in enumerate(pred_ids[:k]):
        if pid in gold_ids:
            dcg += 1.0 / math.log2(i+2)
    return dcg / idcg if idcg > 0 else 0.0

def query(q, use_rerank: bool):
    body = {"query": q["query"], "namespace": q.get("namespace","pmoves"), "k": K, "use_rerank": use_rerank}
    r = requests.post(f"{GATEWAY}/hirag/query", json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    ids = [h["chunk_id"] for h in data["hits"]]
    return ids

def main():
    qs = load_data(DATA)
    rows = []
    for use_rr in (False, True):
        recalls, ndcgs = [], []
        for q in qs:
            ids = query(q, use_rr)
            gold = q.get("gold_ids", [])
            recalls.append(recall_at_k(ids, gold, K))
            ndcgs.append(ndcg_at_k(ids, gold, K))
        rows.append(["rerank="+str(use_rr), np.mean(recalls), np.mean(ndcgs)])
    print(tabulate(rows, headers=["setting","Recall@K","nDCG@K"], floatfmt=".4f"))

if __name__=="__main__":
    main()
