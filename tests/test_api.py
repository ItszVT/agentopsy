from fastapi.testclient import TestClient
from app.main import app
from app import storage


def test_api_home_and_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'app.sqlite')
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        s=client.get('/api/overview').json()
        assert s['total']==12 and s['demo_count']==12
        assert client.get('/api/cases/demo-01').status_code==200
        assert client.get('/api/export.csv').status_code==200


def test_import_replaces_demo_and_outcome_is_unverified(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'app.sqlite')
    with TestClient(app) as client:
        data=b'{"type":"thread.started","thread_id":"x"}\n{"type":"turn.completed"}\n'
        resp=client.post('/api/import',content=data,headers={'content-type':'application/octet-stream'})
        assert resp.status_code==200
        summary=client.get('/api/overview').json()
        assert summary['demo_count']==0 and summary['unknown']==1
        assert summary['solved']==0


def test_import_unsupported_type(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'app.sqlite')
    with TestClient(app) as client:
        resp=client.post('/api/import',content=b'hello',headers={'content-type':'text/plain'})
        assert resp.status_code==415
