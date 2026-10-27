"""Source fidelity and deterministic research with isolated synthetic records."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.analyzer import parse_import
from app.main import app
from app.research import research_findings


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path/'research.sqlite')
    storage.init_db()


def import_rows(rows):
    data = '\n'.join(json.dumps(row) for row in rows).encode()
    _, cases = parse_import(data)
    storage.save_cases(cases)
    return data, cases


def test_import_tracks_exact_source_availability_and_provenance(db):
    rows = [dict(traj_id=str(i), solved=True, step_count=10) for i in range(5)]
    rows[0]['incorrect_error_stage_count'] = 0
    rows[1]['incorrect_error_stage_count'] = 2
    rows[2]['incorrect_error_stage_count'] = None
    rows[3]['incorrect_error_stage_count'] = 'invalid'
    data, cases = import_rows(rows)
    assert [c['metadata']['annotation_status'] for c in cases] == ['explicit_zero','positive','missing','invalid','missing']
    assert all(c['metadata']['manifest_sha256'] == hashlib.sha256(data).hexdigest() for c in cases)
    r = research_findings()
    assert r['coverage'] == dict(explicit_zero=1,positive=1,missing=2,invalid=1,legacy_unknown=0)
    assert r['audited_rows'] == 5
    assert r['manifests'][0]['cases'] == 5


def test_repeat_import_repairs_legacy_without_duplicates_or_other_case_loss(db):
    rows = [dict(traj_id='zero',solved=True,step_count=10,incorrect_error_stage_count=0),
            dict(traj_id='false',solved=False,step_count=20,incorrect_error_stage_count=1),
            dict(traj_id='null',solved=None,step_count=30,incorrect_error_stage_count=0)]
    data, cases = import_rows(rows)
    # Reproduce the earliest parser's zero/missing collapse and null-as-unsolved bug.
    storage.save_cases([dict(c,metadata={},outcome='unsolved' if c['outcome']=='unverified' else c['outcome']) for c in cases])
    other = dict(cases[0],id='other-source',source='Codex JSONL',outcome='unverified')
    storage.save_cases([other])
    before = storage.get_case('other-source')
    assert research_findings()['coverage']['legacy_unknown'] == 2
    with TestClient(app) as client:
        for _ in range(2):
            response=client.post('/api/import',content=data,headers={'content-type':'application/octet-stream'})
            assert response.status_code == 200
            assert response.json()['records'] == dict(unique=3,inserted=0,updated=3,duplicate_rows=0)
            result=client.get('/api/findings').json()
            assert (result['total'],result['solved'],result['unsolved'],result['unverified']) == (3,1,1,1)
            assert result['coverage']['explicit_zero'] == 2
        assert client.get('/api/overview').json()['total'] == 4
    assert storage.get_case('other-source') == before


def test_duplicate_input_rows_do_not_duplicate_cases(db):
    raw=b'{"traj_id":"same","solved":false,"incorrect_error_stage_count":0}\n'*2
    with TestClient(app) as client:
        report=client.post('/api/import',content=raw,headers={'content-type':'application/octet-stream'}).json()
        assert report['records'] == dict(unique=1,inserted=1,updated=0,duplicate_rows=1)
        assert client.get('/api/findings').json()['total'] == 1


@pytest.fixture
def cohort(db):
    rows=[]
    for agent, solved, steps, stages in [('A',True,10,0),('A',False,30,1),('B',True,20,2),('B',False,40,0)]:
        for i in range(10):
            rows.append(dict(traj_id=f'{agent}-{solved}-{i}',agent=agent,category='math',solved=solved,
                             step_count=steps,incorrect_error_stage_count=stages))
    import_rows(rows)
    return research_findings()


def test_research_exact_values_and_supporting_samples(cohort):
    assert (cohort['total'],cohort['verified'],cohort['success_rate']) == (40,40,50)
    assert {f['kind'] for f in cohort['findings']} == {'length','annotation','agent','recurrence'}
    length=next(f for f in cohort['findings'] if f['kind']=='length')
    assert 'median 35, mean 35 steps (n=20)' in length['text']
    assert 'median 15, mean 15 steps (n=20)' in length['text']
    assert 'Median difference (unsolved minus solved): +20 steps' in length['text']
    annotation=next(f for f in cohort['findings'] if f['kind']=='annotation')
    assert '10/20 solved runs (50.00%; 20 stages)' in annotation['text']
    assert '10/20 unsolved runs (50.00%; 10 stages)' in annotation['text']
    assert all(f['sample_size']==len(set(f['case_ids']))==sum(f['group_sizes']) for f in cohort['findings'])
    assert all(f['category']=='math' and min(f['group_sizes'])>=10 and f['limitation'] for f in cohort['findings'])


def test_filters_recompute_and_do_not_cross_categories(cohort):
    import_rows([dict(traj_id=f'coding-{i}',agent='C',category='coding',solved=True,step_count=100) for i in range(10)])
    selected=research_findings(agent='A',category='math')
    assert selected['total'] == 20
    assert not any(f['kind']=='agent' for f in selected['findings'])
    selected_ids={c['id'] for c in selected['cases']}
    assert all(set(f['case_ids'])<=selected_ids for f in selected['findings'])
    assert research_findings(category='coding')['findings'] == []
    assert research_findings(agent="A' OR 1=1 --")['total'] == 0


def test_fingerprints_are_stable_and_change_with_inputs(cohort):
    assert research_findings()['analysis_sha256'] == cohort['analysis_sha256']
    assert research_findings(agent='A')['analysis_sha256'] != cohort['analysis_sha256']
    import_rows([dict(traj_id='extra',agent='A',category='math',solved=False,step_count=5)])
    assert research_findings()['analysis_sha256'] != cohort['analysis_sha256']


def test_missing_fields_do_not_enter_length_or_annotation_findings(db):
    import_rows([dict(traj_id=str(i),agent='A',category='x',solved=(i<10)) for i in range(20)])
    result=research_findings()
    assert result['verified']==20 and result['findings']==[]
    assert result['coverage']['missing']==20


def test_group_size_cutoff_is_applied_to_each_group(db):
    rows=[dict(traj_id=f'edge-{i}',agent='A',category='edge',solved=i<9,
               step_count=10,incorrect_error_stage_count=0) for i in range(19)]
    import_rows(rows)
    assert research_findings()['findings']==[]
    import_rows([dict(traj_id='tenth-solved',agent='A',category='edge',solved=True,
                      step_count=10,incorrect_error_stage_count=0)])
    result=research_findings()
    assert {f['kind'] for f in result['findings']}=={'length','annotation','recurrence'}
    assert all(f['group_sizes']==[10,10] for f in result['findings'])
    assert all(f['sample_size']==20 for f in result['findings'])


def test_unverified_cases_excluded_and_legacy_counts_stay_unknown(db):
    _,cases=import_rows([dict(traj_id='null',solved=None,incorrect_error_stage_count=0)])
    storage.save_cases([dict(cases[0], metadata={})])
    result=research_findings()
    assert result['success_rate'] is None and result['verified']==0
    assert result['coverage']['legacy_unknown']==1


def test_api_empty_demo_and_compatibility(db):
    with TestClient(app) as client:
        result=client.get('/api/findings').json()
        assert result['total']==0 and result['findings']==[]
        assert result['coverage']['explicit_zero']==0
        for route in ['/','/api/overview','/api/cases','/api/performance','/api/failure-lab','/api/export.csv']:
            assert client.get(route).status_code==200


def test_api_filters(cohort):
    with TestClient(app) as client:
        result=client.get('/api/findings',params=dict(agent='B',category='math')).json()
        assert result['total']==20 and result['filters']==dict(agent='B',category='math')
