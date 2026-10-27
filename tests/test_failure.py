"""Failure Lab calculations use isolated synthetic fixtures, never production records."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.analyzer import parse_manifest, parse_codex, parse_import
from app.demo import demo_cases
from app.failure import failure_lab
from app.main import app


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path/'failure.sqlite')
    storage.init_db()
    raw = [
        dict(traj_id='1', agent='A', category='math', solved=True, step_count=10, incorrect_error_stage_count=0),
        dict(traj_id='2', agent='A', category='math', solved=True, step_count=30, incorrect_error_stage_count=2),
        dict(traj_id='3', agent='A', category='math', solved=False, step_count=100, incorrect_error_stage_count=3),
        dict(traj_id='4', agent='B', category='math', solved=False),
        dict(traj_id='5', agent='A', category='math', solved=None, step_count=1000),
        dict(traj_id='6', agent='A', category='coding', solved=True, step_count=0, incorrect_error_stage_count=0),
    ]
    cases = parse_manifest(raw)
    legacy_zero = dict(cases[3], id='legacy-zero', metadata={}, signals=[])
    legacy_positive = dict(cases[2], id='legacy-positive', metadata={}, step_count=50,
                           incorrect_stages=2, signals=['Annotated incorrect stages']*2)
    events = [dict(type='item.completed', item=dict(type='command_execution', command='private command', exit_code=1))]*3
    codex = parse_codex(events+[dict(type='turn.completed')])
    storage.save_cases(cases+[legacy_zero, legacy_positive]+codex+demo_cases())
    return cases


def math(data):
    return next(c for c in data['categories'] if c['category'] == 'math')


def test_outcomes_lengths_annotations_and_distribution(lab):
    data = failure_lab()
    assert (data['total'], data['verified'], data['excluded']) == (9, 7, 2)
    m = math(data)
    assert (m['verified'], m['solved'], m['unsolved'], m['success_rate']) == (6, 2, 4, 33.33)
    assert m['length'] == dict(cases=6, count=4, missing=2, mean=47.5, median=40, small_sample=True)
    assert m['steps']['solved']['median'] == 20
    assert m['steps']['unsolved']['mean'] == 75
    assert m['annotations'] == dict(known_cases=4, missing_cases=2, affected_cases=3, stages=7)
    assert sum(b['solved'] for b in m['distribution']) == 2
    assert sum(b['unsolved'] for b in m['distribution']) == 2
    assert m['distribution'][0]['solved'] == 1
    coding = next(c for c in data['categories'] if c['category'] == 'coding')
    assert coding['length']['median'] == 0
    assert coding['annotations']['known_cases'] == 1
    assert coding['annotations']['stages'] == 0
    assert 'SYNTHETIC' not in json.dumps(data)


def test_patterns_case_counts_are_not_occurrences(lab):
    patterns = {p['name']: p for p in failure_lab()['patterns']}
    assert patterns['Tool error']['affected_cases'] == 1
    assert patterns['Tool error']['measured_occurrences'] == 3
    assert patterns['Repeated command']['measured_occurrences'] == 2
    assert patterns['Annotated incorrect stages']['affected_cases'] == 3
    assert patterns['Annotated incorrect stages']['measured_occurrences'] == 7
    assert patterns['Unsolved benchmark task']['kind'] == 'outcome'
    assert patterns['Unsolved benchmark task']['measured_occurrences'] is None
    assert patterns['Long trajectory']['kind'] == 'heuristic'
    # Overview bars also count affected cases once, even for duplicate labels.
    summary = storage.overview('Tracebench')
    assert next(p['count'] for p in summary['patterns'] if p['name'] == 'Annotated incorrect stages') == 3
    assert 'private command' not in json.dumps(failure_lab())


def test_unknown_occurrences_are_not_inferred_from_issue_count(lab):
    c = dict(lab[0], id='legacy-error', source='Codex JSONL', outcome='failed',
             signals=['Tool error', 'Repeated command'], issue_count=99, metadata={})
    storage.save_cases([c])
    p = next(p for p in failure_lab(agent='A', outcome='failed')['patterns'] if p['name'] == 'Tool error')
    assert p['measured_occurrences'] is None and p['unknown_occurrence_cases'] == 1
    assert failure_lab(outcome='failed')['verified'] == 0


def test_all_filters_apply_to_every_section(lab):
    data = failure_lab(agent='A', category='math', outcome='unsolved', min_steps=100,
                       max_steps=100, signal='Long trajectory')
    assert data['total'] == data['verified'] == 1
    assert math(data)['length']['median'] == 100
    assert math(data)['success_rate'] == 0
    assert all(p['affected_cases'] == 1 for p in data['patterns'])
    assert len(data['cases']) == 1
    assert all(i['case_ids'] == [lab[2]['id']] for i in data['insights'])
    assert data['options']['agent'] == ['A', 'B', 'Codex']
    assert failure_lab(min_steps=0)['total'] == 7  # two unknown lengths excluded
    assert failure_lab(agent="A' OR 1=1 --")['total'] == 0


def test_insights_have_exact_support_and_scope(lab):
    data = failure_lab(category='math')
    insight = next(i for i in data['insights'] if i['kind'] == 'length')
    assert insight['sample_size'] == 4 and len(insight['case_ids']) == 4
    assert '75 steps versus 20' in insight['text']
    assert '+55 steps' in insight['text']
    assert insight['small_sample'] is True
    assert 'does not prove' in insight['limitation']
    records = {c['id']: c for c in data['cases']}
    assert all(records[cid]['category'] == 'math' and records[cid]['steps'] is not None for cid in insight['case_ids'])
    assert not any(i['kind'] == 'length' for i in failure_lab(outcome='solved')['insights'])


def test_empty_and_unverified_only(lab):
    data = failure_lab(agent='absent')
    assert data['total'] == 0 and data['categories'] == data['patterns'] == data['insights'] == data['cases'] == []
    m = math(failure_lab(outcome='unverified', category='math'))
    assert m['success_rate'] is None and m['length']['mean'] is None


def test_small_sample_threshold(lab):
    template = dict(lab[0], category='large', agent='C')
    storage.save_cases([dict(template, id=f'large-{i}') for i in range(10)])
    data = failure_lab(category='large')
    assert data['categories'][0]['small_sample'] is False
    assert data['categories'][0]['length']['small_sample'] is False


@pytest.mark.parametrize('value', [None, -1, True, 'bad', 1.5, '', float('inf'), 2**63, '9'*5000])
def test_invalid_counts_remain_missing(value):
    c = parse_manifest([dict(traj_id='x', step_count=value, incorrect_error_stage_count=value)])[0]
    assert c['metadata'] == dict(steps_known=False, annotation_known=False)
    assert c['step_count'] == c['incorrect_stages'] == 0


def test_explicit_zero_and_string_counts():
    c = parse_manifest([dict(traj_id='x', step_count='0', incorrect_error_stage_count=0)])[0]
    assert c['metadata'] == dict(steps_known=True, annotation_known=True)
    source, cases = parse_import(b'{"traj_id":"missing","solved":false}')
    assert source == 'Tracebench manifest' and cases[0]['metadata']['steps_known'] is False


def test_api_and_existing_views(lab):
    with TestClient(app) as client:
        resp = client.get('/api/failure-lab', params=dict(agent='A', category='math', min_steps=100, max_steps=100, signal='Long trajectory'))
        assert resp.status_code == 200 and resp.json()['total'] == 1
        for params in [dict(min_steps=-1), dict(min_steps='no'), dict(min_steps=5, max_steps=1)]:
            assert client.get('/api/failure-lab', params=params).status_code == 422
        assert client.get('/api/cases/'+lab[0]['id']).json()['metadata']['annotation_known'] is True
        assert client.get('/api/overview').status_code == 200
        assert client.get('/api/performance').status_code == 200
        assert client.get('/api/export.csv').status_code == 200
        assert client.get('/').status_code == 200


def test_old_database_migration_is_additive_and_idempotent(tmp_path, monkeypatch):
    path = tmp_path/'old.sqlite'
    monkeypatch.setattr(storage, 'DB_PATH', path)
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE cases (id TEXT PRIMARY KEY,source TEXT,agent TEXT,
            model TEXT,task TEXT,category TEXT,outcome TEXT,step_count INTEGER,
            issue_count INTEGER,incorrect_stages INTEGER,signals TEXT,events TEXT,
            is_demo INTEGER,note TEXT,created_at TEXT)''')
        db.execute("INSERT INTO cases VALUES ('old','Tracebench','A','M','T','math','solved',0,0,0,'[]','[]',0,'','')")
    storage.init_db()
    storage.init_db()
    assert storage.get_case('old')['metadata'] == {}
    assert failure_lab()['cases'][0]['steps'] is None
    # Reimport updates the same row and makes explicit zeros distinguishable.
    c = dict(parse_manifest([dict(traj_id='old', solved=True, step_count=0, incorrect_error_stage_count=0)])[0], id='old')
    storage.save_cases([c])
    assert failure_lab()['total'] == 1
    assert failure_lab()['cases'][0]['steps'] == 0


def test_overview_and_performance_exclude_missing_steps(lab):
    data = storage.performance_lab(category='math', agent='B')
    assert data['categories'][0]['steps']['unsolved']['mean'] is None
    assert storage.overview('Tracebench')['avg_steps'] == round((10+30+100+1000+0+50)/6, 1)


def test_no_display_limit(lab):
    storage.save_cases([dict(lab[0], id=f'many-{i}', category='many') for i in range(2001)])
    data = failure_lab(category='many')
    assert data['verified'] == len(data['cases']) == 2001


def test_empty_database_with_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path/'demo.sqlite')
    with TestClient(app) as client:
        data = client.get('/api/failure-lab').json()
        assert data['total'] == 0 and data['options']['signal'] == []
