"""Public-demo boundaries and reproducible seeding with synthetic test inputs."""
import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import public_demo, storage
from app.analyzer import parse_import
from app.main import app


@pytest.fixture
def seed(tmp_path, monkeypatch):
    rows=[dict(traj_id=f'public-{i}',agent='A',category='testing',solved=value,
               step_count=10+i,incorrect_error_stage_count=0) for i,value in enumerate([True,False,None])]
    raw='\n'.join(json.dumps(row) for row in rows).encode()
    monkeypatch.setattr(public_demo,'SOURCE_SHA256',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(public_demo,'EXPECTED_COUNTS',dict(total=3,solved=1,unsolved=1,unverified=1))
    prepared=public_demo.prepare_bytes(raw)
    path=tmp_path/'seed.json'
    path.write_text(json.dumps(prepared),encoding='utf-8')
    monkeypatch.setenv('AGENTOPSY_DEMO_SEED',str(path))
    monkeypatch.setenv('AGENTOPSY_MODE','demo-preview')
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'private.sqlite')
    storage.init_db()
    _,cases=parse_import(b'{"type":"turn.completed"}')
    cases[0]['note']='PRIVATE FIXTURE: never publish'
    storage.save_cases(cases)
    return path,raw,cases[0]['id']


def test_seed_checksum_is_required(seed):
    _,raw,_=seed
    with pytest.raises(ValueError,match='checksum mismatch'):
        public_demo.prepare_bytes(raw+b'\n')


def test_seed_rejects_codex_and_duplicates(seed):
    path,_,_=seed
    payload=json.loads(path.read_text())
    payload['cases'][0]['source']='Codex JSONL'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='unsupported'):
        public_demo.load_seed(path)
    payload['cases'][0]['source']='Tracebench'
    payload['cases'][1]['id']=payload['cases'][0]['id']
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='Duplicate'):
        public_demo.load_seed(path)


def test_preview_is_isolated_read_only_and_preserves_unknown_outcomes(seed):
    path,_,private_id=seed
    private_path=storage.DB_PATH
    with TestClient(app) as client:
        demo_path=storage.DB_PATH
        assert demo_path!=private_path
        result=client.get('/api/overview').json()
        assert (result['total'],result['solved'],result['failed'],result['unknown'])==(3,1,1,1)
        assert result['demo_count']==0
        assert client.get('/api/cases/'+private_id).status_code==404
        assert 'PRIVATE FIXTURE' not in client.get('/api/export.csv').text
        health=client.get('/api/health').json()
        assert health['mode']=='demo-preview' and health['read_only'] is True
        assert 'CodeTraceBench' in health['attribution']
        assert client.get('/api/cases',headers={'accept-encoding':'gzip'}).headers['content-encoding']=='gzip'
        research=client.get('/api/findings').json()
        assert research['verified']==2 and research['unverified']==1
        assert research['coverage']['explicit_zero']==3
        with pytest.raises(sqlite3.OperationalError,match='readonly'):
            storage.clear_demo()
        for method,url in [('POST','/api/import'),('DELETE','/api/demo'),('PUT','/api/cases/x'),('PATCH','/new-route')]:
            assert client.request(method,url,content=b'not parsed').status_code==403
        for url in ['/','/api/cases','/api/performance','/api/failure-lab','/api/findings','/api/export.csv']:
            assert client.get(url).status_code==200
        response=client.get('/')
        assert response.headers['x-content-type-options']=='nosniff'
    assert storage.DB_PATH==private_path and storage.get_case(private_id)['note'].startswith('PRIVATE')
    assert not demo_path.exists()
    # A restart reconstructs the same cohort instead of relying on ephemeral SQLite.
    with TestClient(app) as client:
        assert client.get('/api/overview').json()['total']==3


def test_public_requires_data_permission_reference(seed,monkeypatch):
    monkeypatch.setenv('AGENTOPSY_MODE','public')
    monkeypatch.delenv('AGENTOPSY_DATA_PERMISSION_REFERENCE',raising=False)
    with pytest.raises(RuntimeError,match='confirm dataset'):
        with TestClient(app):
            pass
    monkeypatch.setenv('AGENTOPSY_DATA_PERMISSION_REFERENCE','Synthetic test fixture only; not actual dataset permission')
    with TestClient(app) as client:
        assert client.get('/api/health').json()['mode']=='public'


def test_bad_seed_fails_closed_instead_of_using_private_db(seed):
    path,_,private_id=seed
    path.write_text('{}')
    with pytest.raises(ValueError,match='does not match'):
        with TestClient(app):
            pass
    assert storage.get_case(private_id) is not None


def test_unknown_mode_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENTOPSY_MODE','production-typo')
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'should-not-exist.sqlite')
    with pytest.raises(RuntimeError,match='Unknown AGENTOPSY_MODE'):
        with TestClient(app):
            pass
    assert not storage.DB_PATH.exists()


def test_demo_without_lifespan_does_not_read_private_database(seed,monkeypatch):
    monkeypatch.setattr(app.state,'demo_ready',False,raising=False)
    # Omitting the TestClient context deliberately skips lifespan startup.
    client=TestClient(app)
    response=client.get('/api/cases')
    assert response.status_code==503
    assert 'PRIVATE FIXTURE' not in response.text


def test_local_streaming_upload_limit_without_content_length(tmp_path,monkeypatch):
    from app import main
    monkeypatch.setenv('AGENTOPSY_MODE','local')
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'local.sqlite')
    monkeypatch.setattr(main,'MAX_BYTES',30)
    with TestClient(app) as client:
        response=client.post('/api/import',content=iter([b'x'*20,b'x'*20]),headers={'content-type':'application/octet-stream'})
        assert response.status_code==413
        response=client.post('/api/import',content=b'{}',headers={'content-type':'application/octet-stream','content-length':'invalid'})
        assert response.status_code==400
        assert client.get('/api/overview').json()['total']==12


def test_static_path_traversal_is_not_served(seed):
    with TestClient(app) as client:
        response=client.get('/static/%2e%2e/storage.py')
        assert response.status_code in (400,404)
        assert 'sqlite3.connect' not in response.text
