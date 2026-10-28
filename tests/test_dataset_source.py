"""Official-source provenance, notice retention, privacy projection, and comparison."""
import csv
import hashlib
import io
import json

import pytest
from fastapi.testclient import TestClient

from app import public_demo
from app.main import app


@pytest.fixture
def official_seed(tmp_path,monkeypatch):
    rows=[dict(traj_id=str(i),solved=outcome,agent='A',category='test',step_count=25,
               incorrect_error_stage_count=0,annotation_relpath='PRIVATE_PATH',
               source_relpath='PRIVATE_SOURCE',artifact_path='PRIVATE_ARCHIVE',
               incorrect_stages=json.dumps([dict(reasoning='PRIVATE_REASONING',action_ref={'content':'PRIVATE_PROMPT'})]),
               stages=json.dumps([dict(start_step_id=1,end_step_id=25,raw_command='PRIVATE_COMMAND')]))
          for i,outcome in enumerate([True,False,None])]
    raw='\n'.join(json.dumps(r) for r in rows).encode()
    monkeypatch.setattr(public_demo,'SOURCE_SHA256',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(public_demo,'EXPECTED_COUNTS',dict(total=3,solved=1,unsolved=1,unverified=1))
    payload=public_demo.prepare_bytes(raw)
    path=tmp_path/'official.json'
    path.write_text(json.dumps(payload),encoding='utf-8')
    monkeypatch.setenv('AGENTOPSY_MODE','demo-preview')
    monkeypatch.setenv('AGENTOPSY_DEMO_SEED',str(path))
    return path,payload,raw,rows


def test_projection_discards_paths_prompts_and_raw_annotations(official_seed):
    _,payload,_,_=official_seed
    case_data=json.dumps(payload['cases'])
    for secret in ['PRIVATE_PATH','PRIVATE_SOURCE','PRIVATE_ARCHIVE','PRIVATE_REASONING','PRIVATE_PROMPT','PRIVATE_COMMAND']:
        assert secret not in case_data
    for case in payload['cases']:
        assert isinstance(case['incorrect_stages'],int)
        assert case['metadata']['dataset_repo']=='NJU-LINK/CodeTraceBench'
        assert case['metadata']['dataset_license']=='MIT'
        assert case['events'][0]['detail']=='Step range 1 to 25'
    assert payload['license_notices']==public_demo.NOTICES_PATH.read_text(encoding='utf-8')
    assert payload['source_revision']==public_demo.SOURCE_REVISION


@pytest.mark.parametrize('field,value',[('version',1),('source_url','https://huggingface.co/datasets/Contextbench/Tracebench'),
                                        ('source_revision','main'),('license','unknown'),('license_notices','removed')])
def test_old_or_unnoticed_seed_cannot_be_published(official_seed,field,value):
    path,payload,_,_=official_seed
    payload[field]=value
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='does not match'):
        public_demo.load_seed(path)


def test_seed_record_provenance_cannot_be_mirror(official_seed):
    path,payload,_,_=official_seed
    payload['cases'][0]['metadata']['dataset_repo']='Contextbench/Tracebench'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='unsupported'):
        public_demo.load_seed(path)


def test_comparison_distinguishes_raw_schema_and_analytics_changes(official_seed):
    _,_,new,rows=official_seed
    old_rows=[{k:v for k,v in r.items() if k!='annotation_relpath'} for r in rows]
    old='\n'.join(json.dumps(r) for r in old_rows).encode()
    result=public_demo.compare_manifests(old,new)
    assert result['shared_ids']==3
    assert result['raw_differing_fields']=={'annotation_relpath':3}
    assert result['normalized_differing_fields']=={}
    old_rows[0]['solved']=False
    old_changed='\n'.join(json.dumps(r) for r in old_rows).encode()
    assert public_demo.compare_manifests(old_changed,new)['normalized_differing_fields']['outcome']==1


def test_comparison_rejects_duplicate_ids(official_seed):
    _,_,raw,_=official_seed
    with pytest.raises(ValueError,match='Duplicate'):
        public_demo.compare_manifests(raw,raw+b'\n'+raw.splitlines()[0])


def test_served_notices_health_and_csv_retain_license_and_citation(official_seed):
    with TestClient(app) as client:
        health=client.get('/api/health').json()
        assert health['dataset_license']=='MIT'
        assert health['citation_url']=='https://arxiv.org/abs/2604.11641'
        assert '/NJU-LINK/CodeTraceBench/' in health['license_url']
        notices=client.get(health['notices_url'])
        assert notices.status_code==200
        assert 'Kilian A. Lieret and Carlos E. Jimenez' in notices.text
        assert 'Apache License' in notices.text
        exported=client.get('/api/export.csv')
        rows=list(csv.DictReader(io.StringIO(exported.text)))
        assert len(rows)==3
        assert rows[0]['license_notice'].splitlines()==notices.text.splitlines()
        assert all(r['dataset_license']=='MIT' for r in rows)
        assert 'PRIVATE_PROMPT' not in exported.text
        assert 'rel="license"' in exported.headers['link']
