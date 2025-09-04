from fastapi import FastAPI, Body
from typing import Dict, Any
import json
from libs.langextract import extract_text, extract_xml
import os, requests

app = FastAPI(title="PMOVES LangExtract", version="2.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/extract/text")
def extract_text_endpoint(body: Dict[str, Any] = Body(...)):
    document = body.get('text') or ''
    namespace = body.get('namespace') or 'pmoves'
    doc_id = body.get('doc_id') or 'doc'
    res = extract_text(document, namespace, doc_id)
    out = {"chunks": res.get('chunks', []), "errors": res.get('errors', []), "count": len(res.get('chunks', []))}
    _maybe_publish(out)
    return out

@app.post("/extract/xml")
def extract_xml_endpoint(body: Dict[str, Any] = Body(...)):
    xml = body.get('xml') or ''
    namespace = body.get('namespace') or 'pmoves'
    doc_id = body.get('doc_id') or 'doc'
    res = extract_xml(xml, namespace, doc_id)
    out = {"chunks": res.get('chunks', []), "errors": res.get('errors', []), "count": len(res.get('chunks', []))}
    _maybe_publish(out)
    return out

# Backward compatibility alias for XML
@app.post("/extract")
def extract_alias(body: Dict[str, Any] = Body(...)):
    return extract_xml_endpoint(body)

@app.post("/extract/jsonl")
def extract_jsonl(body: Dict[str, Any] = Body(...)):
    if 'xml' in body:
        res = extract_xml(body.get('xml') or '', body.get('namespace') or 'pmoves', body.get('doc_id') or 'doc')
    else:
        res = extract_text(body.get('text') or '', body.get('namespace') or 'pmoves', body.get('doc_id') or 'doc')
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
