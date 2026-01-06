from fastapi import FastAPI, Body
from typing import Dict, Any
import json
import time
from libs.langextract import extract_text, extract_xml
import os, requests
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

app = FastAPI(title="PMOVES LangExtract", version="2.0.0")

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────────────────────
LANGEXTRACT_REQUESTS = Counter(
    "langextract_requests_total",
    "Total LangExtract requests",
    ["endpoint", "status"]
)
LANGEXTRACT_CHUNKS = Counter(
    "langextract_chunks_total",
    "Total chunks extracted"
)
LANGEXTRACT_LATENCY = Histogram(
    "langextract_latency_seconds",
    "LangExtract processing latency in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/extract/text")
def extract_text_endpoint(body: Dict[str, Any] = Body(...)):
    start = time.time()
    try:
        document = body.get('text') or ''
        namespace = body.get('namespace') or 'pmoves'
        doc_id = body.get('doc_id') or 'doc'
        metadata = body.get('observability') or body.get('metadata') or None
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None
        res = extract_text(document, namespace, doc_id, metadata=metadata)
        out = {"chunks": res.get('chunks', []), "errors": res.get('errors', []), "count": len(res.get('chunks', []))}
        LANGEXTRACT_CHUNKS.inc(len(out.get('chunks', [])))
        LANGEXTRACT_REQUESTS.labels(endpoint="text", status="success").inc()
        _maybe_publish(out)
        return out
    except Exception as e:
        LANGEXTRACT_REQUESTS.labels(endpoint="text", status="error").inc()
        raise
    finally:
        LANGEXTRACT_LATENCY.observe(time.time() - start)

@app.post("/extract/xml")
def extract_xml_endpoint(body: Dict[str, Any] = Body(...)):
    start = time.time()
    try:
        xml = body.get('xml') or ''
        namespace = body.get('namespace') or 'pmoves'
        doc_id = body.get('doc_id') or 'doc'
        metadata = body.get('observability') or body.get('metadata') or None
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None
        res = extract_xml(xml, namespace, doc_id, metadata=metadata)
        out = {"chunks": res.get('chunks', []), "errors": res.get('errors', []), "count": len(res.get('chunks', []))}
        LANGEXTRACT_CHUNKS.inc(len(out.get('chunks', [])))
        LANGEXTRACT_REQUESTS.labels(endpoint="xml", status="success").inc()
        _maybe_publish(out)
        return out
    except Exception as e:
        LANGEXTRACT_REQUESTS.labels(endpoint="xml", status="error").inc()
        raise
    finally:
        LANGEXTRACT_LATENCY.observe(time.time() - start)

# Backward compatibility alias for XML
@app.post("/extract")
def extract_alias(body: Dict[str, Any] = Body(...)):
    return extract_xml_endpoint(body)

@app.post("/extract/jsonl")
def extract_jsonl(body: Dict[str, Any] = Body(...)):
    if 'xml' in body:
        metadata = body.get('observability') or body.get('metadata') or None
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None
        res = extract_xml(
            body.get('xml') or '',
            body.get('namespace') or 'pmoves',
            body.get('doc_id') or 'doc',
            metadata=metadata,
        )
    else:
        metadata = body.get('observability') or body.get('metadata') or None
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None
        res = extract_text(
            body.get('text') or '',
            body.get('namespace') or 'pmoves',
            body.get('doc_id') or 'doc',
            metadata=metadata,
        )
    out = {"chunks": res.get('chunks', []), "errors": res.get('errors', []), "count": len(res.get('chunks', []))}
    _maybe_publish(out)
    lines = [json.dumps(c, ensure_ascii=False) for c in out.get('chunks', [])]
    return {"jsonl": "\n".join(lines)}

def _maybe_publish(payload):
    url = os.environ.get('EXTRACT_PUBLISH_URL')
    token = os.environ.get('EXTRACT_PUBLISH_TOKEN')
    if not url: return
    try:
        headers={'content-type':'application/json'}
        if token: headers['Authorization'] = f'Bearer {token}'
        requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
    except Exception:
        pass
