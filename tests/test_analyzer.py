import json
import pytest
from app.analyzer import read_jsonl, parse_import, ImportProblem, parse_manifest, parse_codex


def test_read_jsonl():
    assert read_jsonl(b'{"a":1}\n\n{"b":2}\n')==[{'a':1},{'b':2}]


def test_invalid_json():
    with pytest.raises(ImportProblem,match='line 2'):
        read_jsonl(b'{"a":1}\nBAD')


def test_non_json_object():
    with pytest.raises(ImportProblem):
        read_jsonl(b'[]\n')


def test_manifest_outcome_and_stages():
    row={'traj_id':'a','solved':False,'step_count':32,'incorrect_error_stage_count':2,'stages':json.dumps([{'start_step_id':0,'end_step_id':7}]),'agent':'Terminus2','model':'test','task_name':'Run test','category':'Testing'}
    c=parse_manifest([row])[0]
    assert c['outcome']=='unsolved' and c['incorrect_stages']==2
    assert c['events'][0]['detail']=='Step range 0 to 7'
    assert 'Annotated incorrect stages' in c['signals']


def test_codex_turn_completed_not_success():
    rows=[{'type':'thread.started','thread_id':'t'}, {'type':'turn.completed','usage':{'input_tokens':50}}]
    c=parse_codex(rows)[0]
    assert c['outcome']=='unverified'
    assert '50 input' in c['note']


def test_codex_command_secrets_not_stored():
    secret='SECRET-very-private-token'
    rows=[{'type':'thread.started','thread_id':'t'},
          {'type':'item.completed','item':{'type':'command_execution','command':f'echo {secret}','exit_code':2,'status':'failed'}},
          {'type':'turn.completed'}]
    result=json.dumps(parse_codex(rows))
    assert secret not in result
    assert 'Tool error' in result


def test_codex_run_error():
    c=parse_codex([{'type':'turn.failed'}])[0]
    assert c['outcome']=='failed'


def test_repeat_detection():
    x=[{'type':'item.completed','item':{'type':'command_execution','command':'ls','exit_code':0}}]*3
    c=parse_codex(x+[{'type':'turn.completed'}])[0]
    assert 'Repeated command' in c['signals']


def test_bad_schema():
    with pytest.raises(ImportProblem,match='Unsupported'):
        parse_import(b'{"random":true}')


def test_file_size():
    with pytest.raises(ImportProblem,match='8 MB'):
        read_jsonl(b'a'* (8*1024*1024+1))


def test_manifest_detected():
    source,cases=parse_import(json.dumps({'traj_id':'t','step_count':5,'solved':True}).encode())
    assert source=='Tracebench manifest'
    assert cases[0]['outcome']=='solved'
