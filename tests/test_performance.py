"""Analytics fixtures are synthetic and never inserted into the user's database."""
import json

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.analyzer import parse_manifest
from app.demo import demo_cases
from app.main import app


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'lab.sqlite')
    storage.init_db()
    rows = [
        ('1', 'A', 'math', True, 10),
        ('2', 'A', 'math', False, 30),
        ('3', 'A', 'math', None, 900),
        ('4', 'B', 'math', True, 20),
        ('5', 'A', 'coding', False, 80),
    ]
    cases = parse_manifest([dict(traj_id=i, agent=a, category=c, solved=s, step_count=n)
                            for i, a, c, s, n in rows])
    other = dict(cases[0], id='codex', source='Codex JSONL')
    failed = dict(cases[0], id='failed', outcome='failed')
    storage.save_cases(cases + [other, failed] + demo_cases())
    return storage


def test_rates_categories_and_steps(lab):
    data = lab.performance_lab()
    assert data['total'] == 6 and data['excluded'] == 2
    coding, math = data['categories']
    assert coding['category'] == 'coding' and coding['success_rate'] == 0
    assert math['success_rate'] == 66.7 and math['verified'] == 3
    assert math['excluded'] == 2
    a, b = math['agents']
    assert a['agent'] == 'A' and a['success_rate'] == 50
    assert a['verified'] == 2 and a['total'] == 4
    assert b['success_rate'] == 100
    assert math['steps']['solved'] == dict(count=2, mean=15, median=15)
    assert math['steps']['unsolved'] == dict(count=1, mean=30, median=30)


def test_filters_and_missing_groups(lab):
    data = lab.performance_lab(agent='A', category='math', outcome='unverified')
    group = data['categories'][0]
    assert data['total'] == 1 and group['success_rate'] is None
    assert group['steps']['solved'] == dict(count=0, mean=None, median=None)
    assert data['options']['agent'] == ['A', 'B']
    assert len(data['options']['category']) == 2
    assert lab.performance_lab(agent="A' OR 1=1 --")['total'] == 0
    assert lab.performance_lab(category='absent')['categories'] == []
    assert lab.performance_lab(outcome='solved')['total'] == 2


def test_no_case_list_limit(lab):
    case = parse_manifest([dict(traj_id='many', solved=True, step_count=1, agent='C', category='large')])[0]
    lab.save_cases([dict(case, id=f'large-{i}') for i in range(2005)])
    data = lab.performance_lab(category='large')
    assert data['total'] == 2005
    assert data['categories'][0]['verified'] == 2005


def test_api_filters_and_import(lab):
    with TestClient(app) as client:
        response = client.get('/api/performance', params=dict(agent='A', category='math', outcome='unsolved'))
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1 and data['categories'][0]['success_rate'] == 0
        payload = json.dumps(dict(traj_id='new', solved=True, step_count=12, agent='New', category='new'))
        assert client.post('/api/import', content=payload, headers={'content-type': 'application/octet-stream'}).status_code == 200
        assert client.get('/api/performance', params={'agent': 'New'}).json()['total'] == 1
        assert client.get('/api/cases').status_code == 200
        assert client.get('/api/overview').status_code == 200


def test_empty_lab_excludes_startup_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'empty.sqlite')
    with TestClient(app) as client:
        data = client.get('/api/performance').json()
        assert data['total'] == 0 and data['categories'] == []
        assert data['options'] == dict(agent=[], category=[], outcome=[])


@pytest.mark.parametrize('label', [None, 'false', 'true', 0, 1, [], {}])
def test_manifest_invalid_labels_are_unverified(label):
    case = parse_manifest([dict(traj_id='x', step_count=10, solved=label)])[0]
    assert case['outcome'] == 'unverified'
    assert 'Unsolved benchmark task' not in case['signals']


def test_manifest_missing_label_is_unverified():
    assert parse_manifest([dict(traj_id='x', step_count=10)])[0]['outcome'] == 'unverified'
