import os, json
from typing import Dict, Any
from fastapi import FastAPI, Query, Body, UploadFile, File
from fastapi.staticfiles import StaticFiles
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

HIRAG_URL = os.environ.get('HIRAG_URL','http://hi-rag-gateway-v2:8086')
QDRANT_URL = os.environ.get('QDRANT_URL','http://qdrant:6333')
COLL = os.environ.get('QDRANT_COLLECTION','pmoves_chunks')
SUPA = os.environ.get('SUPA_REST_URL','http://postgrest:3000')
STORAGE_URL = os.environ.get('SUPABASE_STORAGE_URL', 'http://storage:5000')
PUBLIC_STORAGE_BASE = os.environ.get('SUPABASE_PUBLIC_STORAGE_BASE', 'http://localhost:5000')
SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

app=FastAPI(title='Retrieval Eval')
app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
def idx(): return {'ok':True, 'routes':['/samples','/query']}

@app.get('/samples')
def samples(namespace: str = Query('pmoves'), limit: int = Query(20, ge=1, le=200)):
    qc = QdrantClient(url=QDRANT_URL, timeout=20.0)
    it, _ = qc.scroll(collection_name=COLL, scroll_filter=Filter(must=[FieldCondition(key='namespace', match=MatchValue(value=namespace))]), with_payload=True, with_vectors=False, limit=limit)
    out = []
    for p in it:
        out.append({'chunk_id': p.payload.get('chunk_id'), 'doc_id': p.payload.get('doc_id'), 'section_id': p.payload.get('section_id'), 'text': p.payload.get('text','')[:240]})
    return {'namespace': namespace, 'count': len(out), 'items': out}

@app.get('/query')
def run_query(q: str = Query(..., alias='q'), namespace: str = Query('pmoves'), k: int = Query(5, ge=1, le=50)):
    r = requests.post(f"{HIRAG_URL}/hirag/query", headers={'content-type':'application/json'}, data=json.dumps({'query': q, 'namespace': namespace, 'k': k}))
    return r.json()

@app.post('/demo/insert_board')
def demo_insert_board(body: Dict[str, Any] = Body(None)):
    row = body or {
        'title': 'Demo (UI insert)',
        'namespace': 'pmoves',
        'content_url': 's3://outputs/demo.png',
        'status': 'submitted',
        'meta': {'ui': 'realtime-demo'}
    }
    r = requests.post(f"{SUPA}/studio_board", headers={'content-type':'application/json'}, data=json.dumps(row))
    return {'ok': r.ok, 'status': r.status_code, 'resp': (r.json() if r.headers.get('content-type','').startswith('application/json') else r.text)}

@app.post('/demo/insert_error')
def demo_insert_error(body: Dict[str, Any] = Body(None)):
    row = body or {
        'doc_id': 'demo-doc', 'namespace': 'pmoves', 'tag': 'error',
        'message': 'Sample UI error', 'code': 'DEMO_001', 'service': 'ui', 'host': 'localhost', 'severity': 'INFO'
    }
    r = requests.post(f"{SUPA}/it_errors", headers={'content-type':'application/json'}, data=json.dumps(row))
    return {'ok': r.ok, 'status': r.status_code, 'resp': (r.json() if r.headers.get('content-type','').startswith('application/json') else r.text)}

@app.post('/demo/upload_avatar')
def demo_upload_avatar(file: UploadFile = File(...)):
    name = file.filename or 'avatar.png'
    data = file.file.read()
    headers = { 'Authorization': f'Bearer {SERVICE_KEY}', 'content-type': file.content_type or 'application/octet-stream' }
    # Upload to storage API
    r = requests.post(f"{STORAGE_URL}/object/avatars/{name}", headers=headers, data=data)
    ok = r.status_code in (200, 201)
    public_url = f"{PUBLIC_STORAGE_BASE}/object/public/avatars/{name}"
    return {'ok': ok, 'status': r.status_code, 'public_url': public_url}

@app.post('/demo/assign_avatar')
def demo_assign_avatar(body: Dict[str, Any] = Body(...)):
    """Assign avatar_url to the latest studio_board row's meta."""
    avatar_url = (body or {}).get('avatar_url')
    if not avatar_url:
        return {'ok': False, 'error': 'avatar_url required'}
    # fetch latest row
    r = requests.get(f"{SUPA}/studio_board?order=id.desc&limit=1")
    if not r.ok:
        return {'ok': False, 'error': f'fetch latest failed {r.status_code}'}
    rows = r.json() if r.headers.get('content-type','').startswith('application/json') else []
    if not rows:
        # create one instead
        ins = requests.post(f"{SUPA}/studio_board", headers={'content-type':'application/json'}, data=json.dumps({'title':'With Avatar','namespace':'pmoves','content_url':'','status':'submitted','meta':{'avatar_url': avatar_url}}))
        return {'ok': ins.ok, 'created': True, 'status': ins.status_code}
    row = rows[0]
    rid = row.get('id')
    meta = row.get('meta') or {}
    meta['avatar_url'] = avatar_url
    pr = requests.patch(f"{SUPA}/studio_board?id=eq.{rid}", headers={'content-type':'application/json'}, data=json.dumps({'meta': meta}))
    return {'ok': pr.ok, 'status': pr.status_code}

@app.get('/demo/agents')
def demo_agents(limit: int = Query(10, ge=1, le=100)):
    r = requests.get(f"{SUPA}/pmoves_core.agent?order=created_at.desc&limit={limit}")
    return {'ok': r.ok, 'status': r.status_code, 'items': (r.json() if r.headers.get('content-type','').startswith('application/json') else [])}

@app.post('/demo/agent_upsert')
def demo_agent_upsert(body: Dict[str, Any] = Body(...)):
    name = (body or {}).get('name'); role = (body or {}).get('role', '')
    avatar_url = (body or {}).get('avatar_url')
    if not name:
        raise Exception('name required')
    row = {'name': name, 'role': role}
    if avatar_url: row['avatar_url'] = avatar_url
    r = requests.post(f"{SUPA}/pmoves_core.agent", headers={'content-type':'application/json'}, data=json.dumps(row))
    return {'ok': r.ok, 'status': r.status_code, 'resp': (r.json() if r.headers.get('content-type','').startswith('application/json') else r.text)}

@app.post('/demo/agent_assign_avatar')
def demo_agent_assign_avatar(body: Dict[str, Any] = Body(...)):
    agent_id = (body or {}).get('id'); name = (body or {}).get('name'); avatar_url = (body or {}).get('avatar_url')
    if not avatar_url:
        return {'ok': False, 'error': 'avatar_url required'}
    if agent_id:
        where = f"id=eq.{agent_id}"
    elif name:
        where = f"name=eq.{requests.utils.quote(name)}"
    else:
        return {'ok': False, 'error': 'provide id or name'}
    r = requests.patch(f"{SUPA}/pmoves_core.agent?{where}", headers={'content-type':'application/json'}, data=json.dumps({'avatar_url': avatar_url}))
    return {'ok': r.ok, 'status': r.status_code}

if __name__=='__main__':
    import uvicorn; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('EVAL_HTTP_PORT', '8090')))
