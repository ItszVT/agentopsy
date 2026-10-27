"""Privacy-preserving ingestion and heuristic analysis.

Raw prompts, command contents, tool outputs and private paths are never persisted.
Tracebench manifests contain aggregate trajectory metadata rather than full actions.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

MAX_BYTES = 8 * 1024 * 1024
MAX_LINES = 5000


class ImportProblem(ValueError):
    pass


def read_jsonl(data: bytes):
    if len(data) > MAX_BYTES:
        raise ImportProblem('File exceeds the 8 MB limit. Import a smaller JSONL sample.')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ImportProblem('File must use UTF-8 encoding.') from exc
    results = []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if n > MAX_LINES:
            raise ImportProblem('The file has too many lines. Import up to 5,000 lines.')
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ImportProblem(f'Invalid JSON on line {n}: {exc.msg}') from exc
        if not isinstance(value, dict):
            raise ImportProblem(f'Line {n} must be a JSON object.')
        results.append(value)
    if not results:
        raise ImportProblem('The JSONL file does not contain any records.')
    return results


def _number(value, default=0):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _known_count(value):
    """Accept nonnegative integers and integer strings, never coerce missing to known zero."""
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        if len(value) > 19 or not value.isascii() or not value.isdecimal():
            return False
        value = int(value)
    return isinstance(value, int) and 0 <= value <= 9223372036854775807


def _safe_label(value, max_chars=80):
    # No free-form source strings used for sensitive log fields.
    return str(value or 'Unknown')[:max_chars]


def _short_hash(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:14]


def _load_nested(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            p = json.loads(value)
            if isinstance(p, list):
                return p
        except json.JSONDecodeError:
            pass
    return []


def parse_manifest(rows):
    """One case per Tracebench manifest row; no unsupported step replay."""
    cases = []
    for idx, row in enumerate(rows):
        if 'traj_id' not in row:
            raise ImportProblem(f'Row {idx+1} is not a supported Tracebench manifest.')
        task = _safe_label(row.get('task_name') or row.get('category') or 'Benchmark task', 100)
        steps_known = _known_count(row.get('step_count'))
        annotation_known = _known_count(row.get('incorrect_error_stage_count'))
        count = int(row['step_count']) if steps_known else 0
        incorrect = int(row['incorrect_error_stage_count']) if annotation_known else 0
        stages = _load_nested(row.get('stages'))
        signals = []
        if row.get('solved') is False:
            signals.append('Unsolved benchmark task')
        if incorrect:
            signals.append('Annotated incorrect stages')
        if count >= 100:
            signals.append('Long trajectory')
        events = []
        for n, stage in enumerate(stages[:75], start=1):
            if not isinstance(stage, dict):
                continue
            start = stage.get('start_step_id')
            end = stage.get('end_step_id')
            events.append({
                'index': n,
                'label': f'Stage {n}',
                'detail': f'Step range {start} to {end}' if start is not None and end is not None else 'Stage boundary recorded',
                'kind': 'stage', 'status': 'recorded'
            })
        # An incorrect stage count is verified metadata, but the index of each such
        # stage is not inferred unless the schema provides a direct mapping.
        cases.append({
            'id': 'tb-' + _short_hash(row['traj_id']),
            'source': 'Tracebench', 'agent': _safe_label(row.get('agent')),
            'model': _safe_label(row.get('model')),
            'task': task, 'category': _safe_label(row.get('category') or 'Benchmark'),
            'outcome': ('solved' if row.get('solved') is True else
                        'unsolved' if row.get('solved') is False else 'unverified'),
            'step_count': count, 'issue_count': incorrect,
            'incorrect_stages': incorrect, 'signals': signals,
            'events': events, 'is_demo': False,
            'metadata': {'steps_known': steps_known, 'annotation_known': annotation_known},
            'note': ('Stage overview reconstructed from manifest metadata. Actual tool actions '
                     'require the separately published trajectory artifact.'),
            'created_at': _safe_label(row.get('generated_at') or ''),
        })
    return cases


def _item_type(item):
    allowed = {'command_execution':'Command execution', 'file_change':'File change',
               'mcp_tool_call':'MCP tool call', 'web_search':'Web search',
               'agent_message':'Agent message', 'reasoning':'Reasoning step',
               'plan_update':'Plan update'}
    return allowed.get(str(item.get('type','')), 'Agent action')


def parse_codex(rows):
    """Treat turn.completed as execution completion, never verified task success."""
    # Group thread IDs: codex exec --json typically one task per stream.
    thread_id = 'session-' + _short_hash(json.dumps(rows[:3],sort_keys=True))
    events = []
    pending = {}
    issues = Counter()
    command_hashes = []
    finished = False
    explicit_failure = False
    input_tokens = 0
    output_tokens = 0
    for row in rows:
        typ = row.get('type', '')
        if typ == 'thread.started':
            thread_id = _safe_label(row.get('thread_id') or thread_id)
        elif typ.startswith('item.'):
            item = row.get('item') or {}
            if not isinstance(item, dict):
                continue
            name = _item_type(item)
            status = str(item.get('status') or ('recorded' if typ=='item.started' else 'completed'))
            iid = str(item.get('id') or len(events))
            if typ == 'item.started':
                pending[iid] = item
                continue
            if typ not in ('item.completed', 'item.failed'):
                continue
            previous = pending.pop(iid, {})
            command = item.get('command') or previous.get('command')
            if name == 'Command execution' and isinstance(command, str):
                command_hashes.append(hashlib.sha256(command.encode('utf-8')).hexdigest())
            code = item.get('exit_code')
            bad = typ == 'item.failed' or status in ('failed','error') or (isinstance(code,int) and code!=0)
            if bad:
                issues['Tool error'] += 1
            detail = 'Exit code ' + str(code) if isinstance(code,int) else ('Action failed' if bad else 'Action completed')
            events.append({'index':len(events)+1, 'label':name,
                           'detail':detail,'kind':'tool','status':'error' if bad else 'ok'})
        elif typ == 'turn.failed' or typ == 'error':
            explicit_failure = True
            issues['Run error'] += 1
            events.append({'index':len(events)+1,'label':'Run error','detail':'Recorded execution error',
                           'kind':'error','status':'error'})
        elif typ == 'turn.completed':
            finished = True
            usage = row.get('usage') or {}
            input_tokens += _number(usage.get('input_tokens'))
            output_tokens += _number(usage.get('output_tokens'))
    repeated = sum(1 for i in range(1, len(command_hashes)) if command_hashes[i]==command_hashes[i-1])
    if repeated >= 2:
        issues['Repeated command'] += repeated
    if not finished and not explicit_failure:
        issues['Incomplete trace'] += 1
    signals = list(issues)
    if not signals:
        signals = ['No rule-based anomaly found']
    return [{
        'id': 'cx-' + _short_hash(thread_id + str(len(rows))),
        'source': 'Codex JSONL', 'agent': 'Codex', 'model': 'Not recorded',
        'task': 'Imported Codex session', 'category': 'Coding workflow',
        'outcome': 'failed' if explicit_failure else 'unverified',
        'step_count': len(events), 'issue_count': sum(issues.values()),
        'incorrect_stages': 0, 'signals':signals,'events':events[:500],
        'is_demo':False,
        'metadata': {'steps_known': True, 'annotation_known': False,
                     'signal_counts': dict(issues)},
        'note': (f'Codex emitted {input_tokens:,} input and {output_tokens:,} output tokens. '
                 'A completed turn is not proof the task succeeded. Raw commands, prompts, '
                 'tool outputs, and file paths were not saved.'),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }]


def parse_import(data: bytes):
    rows = read_jsonl(data)
    if all('traj_id' in row for row in rows):
        cases = parse_manifest(rows)
        digest = hashlib.sha256(data).hexdigest()
        for row, case in zip(rows, cases):
            value = row.get('incorrect_error_stage_count')
            status = ('explicit_zero' if case['metadata']['annotation_known'] and int(value) == 0 else
                      'positive' if case['metadata']['annotation_known'] else
                      'missing' if value is None else 'invalid')
            case['metadata'].update(manifest_sha256=digest, manifest_rows=len(rows),
                                    annotation_status=status)
        return 'Tracebench manifest', cases
    if all('type' in row for row in rows):
        return 'Codex execution log', parse_codex(rows)
    raise ImportProblem('Unsupported JSONL format. Upload a Tracebench manifest or codex exec --json output.')
