import os
import pytest
from app import storage
from app.demo import demo_cases

@pytest.fixture()
def db(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'test.sqlite')
    storage.init_db()
    return storage


def test_save_and_read(db):
    cases=demo_cases()
    assert db.save_cases(cases)==12
    assert len(db.get_cases())==12
    assert db.get_case('demo-01')['events']
    assert db.overview()['total']==12


def test_source_and_filter(db):
    db.save_cases(demo_cases())
    assert len(db.get_cases(status='solved'))==6
    assert len(db.get_cases(source='not-a-source'))==0
    assert len(db.get_cases(q='authentication'))==1


def test_idempotence(db):
    db.save_cases(demo_cases())
    db.save_cases(demo_cases())
    assert db.overview()['total']==12


def test_remove_demo(db):
    db.save_cases(demo_cases())
    assert db.clear_demo()==12
    assert db.overview()['total']==0
