"""Harmless spreadsheet-injection cases; never execute formulas or open a sheet."""
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import _csv_cell, app


@pytest.mark.parametrize('text', [
    '=1+1', '+1+1', '-1+1', '@SUM(1,1)',
    ' =1+1', '\t=1+1', '\r=1+1', '\n=1+1', '\r\n=1+1',
    '\x00=1+1', '\x1b=1+1', '\x7f=1+1', '\x85=1+1',
    '\u00a0=1+1', '\u2003=1+1', '\u202f=1+1', '\u3000=1+1',
    '\u200b=1+1', '\ufeff=1+1', '\u202e=1+1', '\u2066=1+1',
    '\u0301=1+1',
    '\uff1d1+1', '\uff0b1+1', '\uff0d1+1', '\uff20SUM(1,1)',
    '\ufe661+1', '\ufe621+1', '\ufe631+1', '\ufe6bSUM(1,1)',
    '\u207a1+1', '\u22121+1', '\u27951+1', '\u27961+1',
    '=1+1";,=1+1', '=1+1\'";,=1+1', '-42', ' ordinary text',
])
def test_spreadsheet_sensitive_text_is_prefixed_without_rewriting(text):
    assert _csv_cell(text) == "'" + text


@pytest.mark.parametrize('value', [0, 42, -42, 1.25, -1.25, True, False, None])
def test_actual_numeric_and_nontext_values_are_unchanged(value):
    assert _csv_cell(value) is value


@pytest.mark.parametrize('text', [
    '', 'ordinary task', '123', '00123', 'MIT', "'already text",
    'a=b+c-d@example', 'say "hello", then; continue',
    'first line\n=1+1', 'first line\r\n+1+1', 'café',
])
def test_ordinary_text_is_unchanged(text):
    assert _csv_cell(text) == text


def test_import_export_quotes_fields_preserves_columns_and_database(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENTOPSY_MODE', 'local')
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path/'local.sqlite')
    task = '=1+1";,=1+1\nnext line'
    category = 'first line\r\n=1+1, "still one field"; end'
    manifest = dict(traj_id='csv-security', task_name=task, agent='\ufeff+1+1',
                    model='\uff20SUM(1,1)', category=category, solved=False,
                    step_count=42, incorrect_error_stage_count=0)
    with TestClient(app) as client:
        assert client.post('/api/import', content=json.dumps(manifest).encode(),
                           headers={'content-type':'application/octet-stream'}).status_code == 200
        original = storage.get_cases()[0]
        response = client.get('/api/export.csv')
        assert response.status_code == 200
        assert 'attachment; filename="agentopsy_cases.csv"' == response.headers['content-disposition']
        rows = list(csv.reader(io.StringIO(response.text, newline=''), strict=True))
        assert rows[0] == ['id','source','agent','model','task','category','outcome',
                           'step_count','issue_count','incorrect_stages','is_demo']
        assert len(rows) == 2 and len(rows[1]) == len(rows[0])
        exported = dict(zip(rows[0], rows[1]))
        assert exported['task'] == "'" + task
        assert exported['agent'] == "'" + manifest['agent']
        assert exported['model'] == "'" + manifest['model']
        assert exported['category'] == category
        assert exported['step_count'] == '42'
        assert exported['incorrect_stages'] == '0'
        assert response.text.startswith('"id","source",')
        assert '"\'=1+1"";,=1+1\nnext line"' in response.text
        assert storage.get_cases()[0] == original
        detail = client.get('/api/cases/'+original['id']).json()
        assert detail['task'] == task and detail['category'] == category


def test_csv_helper_applies_to_every_string_field_without_corrupting_structure(monkeypatch):
    # Exercise stored string fields beyond the usual importer labels.
    from app import main
    fields = ['id','source','agent','model','task','category','outcome',
              'step_count','issue_count','incorrect_stages','is_demo']
    record = {field:'=1+1";,\nnext' for field in fields}
    record.update(step_count=-42, issue_count=0, incorrect_stages=1, is_demo=False)
    monkeypatch.setattr(main, 'get_cases', lambda **kwargs:[record])
    monkeypatch.setattr(app.state, 'read_only', False, raising=False)
    response = main.export_csv()
    # The endpoint builds a single CSV chunk without changing the supplied row.
    import asyncio
    async def body():
        return ''.join([chunk async for chunk in response.body_iterator])
    rows = list(csv.DictReader(io.StringIO(asyncio.run(body()), newline='')))
    assert len(rows) == 1
    for field in fields:
        expected = "'"+record[field] if isinstance(record[field], str) else str(record[field])
        assert rows[0][field] == expected
    assert record['id'].startswith('=')
