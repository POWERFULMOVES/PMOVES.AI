from pathlib import Path
import sys
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, ANY

# Import the service module
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
yt = __import__('yt')

def test_info(monkeypatch):
    class DummyYDL:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def extract_info(self, url, download):
            return {
                'id': 'abc123',
                'title': 'Video',
                'uploader': 'Uploader',
                'duration': 10,
                'webpage_url': url
            }
    monkeypatch.setattr(yt.yt_dlp, 'YoutubeDL', DummyYDL)
    client = TestClient(yt.app)
    resp = client.post('/yt/info', json={'url': 'https://youtu.be/abc123'})
    assert resp.status_code == 200
    data = resp.json()['info']
    assert data['id'] == 'abc123'
    assert data['title'] == 'Video'

def test_download(monkeypatch):
    class DummyYDL:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def extract_info(self, url, download):
            return {
                'id': 'abc123',
                'title': 'Video',
                'requested_downloads': [{'_filename': '/tmp/abc123.mp4'}]
            }
    monkeypatch.setattr(yt.yt_dlp, 'YoutubeDL', DummyYDL)
    upload = MagicMock(return_value='http://s3/abc123.mp4')
    monkeypatch.setattr(yt, 'upload_to_s3', upload)
    supa = MagicMock()
    monkeypatch.setattr(yt, 'supa_insert', supa)
    pub = MagicMock()
    monkeypatch.setattr(yt, '_publish_event', pub)
    client = TestClient(yt.app)
    resp = client.post('/yt/download', json={'url': 'https://youtu.be/abc123', 'bucket': 'bkt', 'namespace': 'ns'})
    assert resp.status_code == 200
    assert supa.call_count == 2
    supa.assert_any_call('studio_board', ANY)
    supa.assert_any_call('videos', ANY)
    pub.assert_called_once()

def test_transcript(monkeypatch):
    class DummyResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {'content-type': 'application/json'}
        def json(self):
            return {'language': 'en', 'text': 'hi', 'segments': [], 's3_uri': 's3://bucket/audio.m4a'}
        def raise_for_status(self):
            pass
        @property
        def ok(self):
            return True
    monkeypatch.setattr(yt.requests, 'post', lambda *a, **k: DummyResp())
    supa = MagicMock()
    monkeypatch.setattr(yt, 'supa_insert', supa)
    pub = MagicMock()
    monkeypatch.setattr(yt, '_publish_event', pub)
    client = TestClient(yt.app)
    resp = client.post('/yt/transcript', json={'video_id': 'abc123'})
    assert resp.status_code == 200
    supa.assert_called_once()
    pub.assert_called_once()

def test_summarize(monkeypatch):
    monkeypatch.setattr(yt, 'supa_get', lambda *a, **k: [{'text': 'hello world', 'meta': {}}])
    class DummyResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {'content-type': 'application/json'}
        def json(self):
            return {'response': 'summary'}
        def raise_for_status(self):
            pass
    monkeypatch.setattr(yt.requests, 'post', lambda *a, **k: DummyResp())
    supa_upd = MagicMock()
    monkeypatch.setattr(yt, 'supa_update', supa_upd)
    pub = MagicMock()
    monkeypatch.setattr(yt, '_publish_event', pub)
    client = TestClient(yt.app)
    resp = client.post('/yt/summarize', json={'video_id': 'abc123'})
    assert resp.status_code == 200
    supa_upd.assert_called_once()
    pub.assert_called_once()

def test_emit(monkeypatch):
    def fake_supa_get(table, match):
        if table == 'videos':
            return [{'video_id': 'abc123', 'title': 'Video'}]
        if table == 'transcripts':
            return [{'text': 'hello world', 'meta': {'segments': [{'start':0,'end':1,'text':'hello'}]}}]
        return []
    monkeypatch.setattr(yt, 'supa_get', fake_supa_get)
    monkeypatch.setattr(yt, 'YT_SEG_AUTOTUNE', False)
    chunks = [{'doc_id': 'yt:abc123', 'section_id': None, 'chunk_id': 'yt:abc123:0', 'text': 'hello', 'namespace': 'pmoves', 'payload': {}}]
    monkeypatch.setattr(yt, '_segment_from_whisper_segments', lambda *a, **k: chunks)
    class DummyResp:
        def __init__(self, data=None):
            self.status_code = 200
            self.headers = {'content-type': 'application/json'}
            self._data = data or {}
        def json(self):
            return self._data
        def raise_for_status(self):
            pass
    def fake_post(url, *args, **kwargs):
        if 'upsert-batch' in url:
            return DummyResp({'upserted': 1, 'lexical_indexed': True})
        return DummyResp({})
    monkeypatch.setattr(yt.requests, 'post', fake_post)
    client = TestClient(yt.app)
    resp = client.post('/yt/emit', json={'video_id': 'abc123'})
    assert resp.status_code == 200
    assert resp.json()['chunks'] == 1
