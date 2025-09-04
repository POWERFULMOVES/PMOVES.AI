
import os, json, math
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, SearchRequest
from sentence_transformers import SentenceTransformer, CrossEncoder
from FlagEmbedding import FlagReranker

# Optional providers
try:
    import cohere
except Exception:
    cohere = None
try:
    from openai import AzureOpenAI
except Exception:
    AzureOpenAI = None

QDRANT_URL = os.environ.get("QDRANT_URL","http://qdrant:6333")
COLL = os.environ.get("QDRANT_COLLECTION","pmoves_chunks")
MODEL = os.environ.get("SENTENCE_MODEL","all-MiniLM-L6-v2")

# Reranker provider switch
RERANK_PROVIDER = os.environ.get("RERANK_PROVIDER","flag").lower()  # flag|qwen|cohere|azure
RERANK_ENABLE = os.environ.get("RERANK_ENABLE","true").lower()=="true"
RERANK_MODEL = os.environ.get("RERANK_MODEL","BAAI/bge-reranker-base")
RERANK_TOPN = int(os.environ.get("RERANK_TOPN","50"))
RERANK_K = int(os.environ.get("RERANK_K","10"))

# Cohere
COHERE_API_KEY = os.environ.get("COHERE_API_KEY","")
COHERE_RERANK_MODEL = os.environ.get("COHERE_RERANK_MODEL","rerank-english-v3.0")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT","")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY","")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT","gpt-4o-mini")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION","2024-06-01")

NAMESPACE_DEFAULT = os.environ.get("INDEXER_NAMESPACE","pmoves")

qdrant = QdrantClient(url=QDRANT_URL, timeout=30.0)
embedder = SentenceTransformer(MODEL)

# --- Reranker providers ---
class BaseReranker:
    name = "base"
    def score(self, query: str, texts: List[str]) -> List[float]:
        raise NotImplementedError

class FlagBGEReranker(BaseReranker):
    name = "flag"
    def __init__(self, model_name: str):
        self.model_name = model_name
        try:
            self.re = FlagReranker(model_name, use_fp16=True)
        except Exception as e:
            print("FlagReranker init failed:", e)
            self.re = None
    def score(self, query, texts):
        if self.re is None: return [0.0]*len(texts)
        pairs = [[query, t] for t in texts]
        scores = self.re.compute_score(pairs, normalize=True)  # already 0..1
        return [float(s) for s in scores]

class QwenReranker(BaseReranker):
    name = "qwen"
    def __init__(self, model_name: str = "Qwen/Qwen3-Reranker-4B"):
        self.model_name = model_name
        try:
            self.ce = CrossEncoder(self.model_name, max_length=512, device="cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else None)
        except Exception as e:
            print("Qwen CrossEncoder init failed:", e)
            self.ce = None
    @staticmethod
    def _sigmoid(x: float) -> float:
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0
    def score(self, query, texts):
        if self.ce is None: return [0.0]*len(texts)
        pairs = [(query, t) for t in texts]
        raw = self.ce.predict(pairs, convert_to_numpy=True)  # logits
        # normalize via sigmoid to 0..1
        return [float(self._sigmoid(v)) for v in raw]

class CohereReranker(BaseReranker):
    name = "cohere"
    def __init__(self, api_key: str, model_name: str):
        if not cohere:
            raise RuntimeError("cohere package not installed")
        self.client = cohere.Client(api_key)
        self.model_name = model_name
    def score(self, query, texts):
        resp = self.client.rerank(query=query, documents=[{"text": t} for t in texts], model=self.model_name, top_n=len(texts))
        # Map by index in original order
        scores = [0.0]*len(texts)
        for r in resp.results:
            # r.index is position in input list
            try:
                scores[r.index] = float(r.relevance_score)
            except Exception:
                pass
        # cohere scores are already 0..1-ish
        return scores

class AzureOpenAIReranker(BaseReranker):
    name = "azure"
    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str):
        if not AzureOpenAI:
            raise RuntimeError("openai package not installed")
        if not (endpoint and api_key and deployment):
            raise RuntimeError("Missing Azure OpenAI env")
        self.client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
        self.deployment = deployment
    def score(self, query, texts):
        # Ask model to score each text 0..1; keep prompt compact
        MAX = min(len(texts), 50)
        items = [{"id": i, "text": texts[i][:1200]} for i in range(MAX)]
        prompt = "You are a retrieval reranker. For each item, output a JSON list of objects {{id:int, score:float}} with scores in [0,1] for how relevant the item is to the user query.\n"
        prompt += f"Query: {query}\nItems:\n"
        for it in items:
            prompt += f"- id: {it['id']}, text: {it['text']}\n"
        prompt += "Respond with JSON only."
        try:
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role":"user","content": prompt}],
                temperature=0.0,
                max_tokens=512,
                response_format={"type":"json_object"}
            )
            txt = resp.choices[0].message.content
            data = json.loads(txt) if isinstance(txt, str) else txt
            # allow either {"scores":[...]} or directly list
            arr = data.get("scores") if isinstance(data, dict) else data
            if not isinstance(arr, list): arr = data
            scores = [0.0]*len(texts)
            for obj in arr:
                idx = obj.get("id")
                sc = float(obj.get("score", 0.0))
                if 0 <= idx < len(texts):
                    scores[idx] = sc
            return scores
        except Exception as e:
            print("Azure rerank error:", e)
            return [0.0]*len(texts)

# init selected provider
provider_name = RERANK_PROVIDER
reranker = None
try:
    if provider_name == "qwen":
        reranker = QwenReranker(os.environ.get("QWEN_RERANK_MODEL","Qwen/Qwen3-Reranker-4B"))
    elif provider_name == "cohere":
        reranker = CohereReranker(COHERE_API_KEY, COHERE_RERANK_MODEL) if COHERE_API_KEY else None
    elif provider_name == "azure":
        reranker = AzureOpenAIReranker(AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION)
    else:
        # default to flag/bge
        reranker = FlagBGEReranker(RERANK_MODEL)
except Exception as e:
    print("Reranker provider init failed:", e)
    reranker = None

class QueryReq(BaseModel):
    query: str
    namespace: str = Field(default=NAMESPACE_DEFAULT)
    k: int = 10
    alpha: float = 0.7
    use_rerank: Optional[bool] = None
    rerank_topn: Optional[int] = None
    rerank_k: Optional[int] = None

class QueryHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    rerank_score: Optional[float] = None
    payload: Dict[str, Any] = {}

class QueryResp(BaseModel):
    query: str
    k: int
    used_rerank: bool
    rerank_provider: Optional[str] = None
    hits: List[QueryHit]

app = FastAPI(title="PMOVES Hi-RAG Gateway v2 (with rerank providers)", version="2.1.0")

@app.get("/hirag/admin/stats")
def stats():
    return {
        "rerank_enabled": RERANK_ENABLE,
        "rerank_provider": provider_name,
        "rerank_model": RERANK_MODEL if provider_name in ("flag","bge") else (
            os.environ.get("QWEN_RERANK_MODEL") if provider_name=="qwen" else (
                COHERE_RERANK_MODEL if provider_name=="cohere" else AZURE_OPENAI_DEPLOYMENT
            )
        ),
        "rerank_loaded": reranker is not None
    }

@app.post("/hirag/query", response_model=QueryResp)
def hirag_query(req: QueryReq = Body(...)):
    vec = embedder.encode(req.query, normalize_embeddings=True).tolist()
    # vector search
    must = [FieldCondition(key="namespace", match=MatchValue(value=req.namespace))]
    sr = SearchRequest(
        vector=vec, limit=max(req.k, RERANK_TOPN),
        filter=Filter(must=must),
        with_payload=True, with_vectors=False
    )
    hits = QdrantClient(url=QDRANT_URL).search(collection_name=COLL, search_request=sr)

    base = [{
        "chunk_id": h.payload.get("chunk_id") or h.id,
        "text": h.payload.get("text",""),
        "score": float(h.score),
        "payload": h.payload
    } for h in hits]

    enable = req.use_rerank if req.use_rerank is not None else RERANK_ENABLE
    topn = req.rerank_topn or RERANK_TOPN
    outk = req.rerank_k or req.k or RERANK_K

    used = False
    if enable and reranker is not None and base:
        pool = base[:topn]
        scores = reranker.score(req.query, [p["text"] for p in pool])
        # normalize scores 0..1 just in case
        norm = []
        mn, mx = (min(scores), max(scores)) if scores else (0.0, 0.0)
        for s in scores:
            if mx > mn:
                norm.append((s - mn) / (mx - mn))
            else:
                norm.append(0.0)
        for p, s in zip(pool, norm):
            p["rerank_score"] = float(s)
            p["score"] = float(p["score"] * (0.5 + 0.5*s))
        pool.sort(key=lambda x: x["score"], reverse=True)
        base = pool[:outk]
        used = True
    else:
        base = base[:req.k]

    return {
        "query": req.query,
        "k": len(base),
        "used_rerank": used,
        "rerank_provider": provider_name if used else None,
        "hits": base
    }
