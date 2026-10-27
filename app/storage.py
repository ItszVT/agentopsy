"""SQLite aggregates and case storage. All evidence is sanitized before insertion."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get('AGENTOPSY_DB', Path(__file__).resolve().parent.parent/'data'/'agentopsy.sqlite'))
READ_ONLY = False


@contextmanager
def connection():
    if READ_ONLY:
        conn = sqlite3.connect(DB_PATH.resolve().as_uri()+'?mode=ro', uri=True)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS cases (
          id TEXT PRIMARY KEY, source TEXT NOT NULL, agent TEXT NOT NULL,
          model TEXT NOT NULL, task TEXT NOT NULL, category TEXT NOT NULL,
          outcome TEXT NOT NULL, step_count INTEGER NOT NULL,
          issue_count INTEGER NOT NULL, incorrect_stages INTEGER NOT NULL,
          signals TEXT NOT NULL, events TEXT NOT NULL, is_demo INTEGER NOT NULL,
          note TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_cases_source ON cases(source);
        CREATE INDEX IF NOT EXISTS ix_cases_outcome ON cases(outcome);
        ''')
        if 'metadata' not in {r['name'] for r in db.execute('PRAGMA table_info(cases)')}:
            db.execute("ALTER TABLE cases ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")


def save_cases(cases):
    with connection() as db:
        for c in cases:
            db.execute('''INSERT INTO cases
                 (id,source,agent,model,task,category,outcome,step_count,issue_count,
                  incorrect_stages,signals,events,is_demo,note,created_at,metadata)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET
                 source=excluded.source, agent=excluded.agent, model=excluded.model,
                 task=excluded.task, category=excluded.category, outcome=excluded.outcome,
                 step_count=excluded.step_count, issue_count=excluded.issue_count,
                 incorrect_stages=excluded.incorrect_stages, signals=excluded.signals,
                 events=excluded.events, is_demo=excluded.is_demo,
                 note=excluded.note, created_at=excluded.created_at, metadata=excluded.metadata''',(
                  c['id'],c['source'],c['agent'],c['model'],c['task'],c['category'],
                  c['outcome'],c['step_count'],c['issue_count'],c['incorrect_stages'],
                  json.dumps(c['signals']),json.dumps(c['events']),int(c['is_demo']),
                  c['note'],c['created_at'],json.dumps(c.get('metadata', {}))))
    return len(cases)


def _to_case(row, with_events=False):
    d = dict(row)
    d['signals'] = json.loads(d['signals'])
    d['metadata'] = json.loads(d['metadata'])
    d['is_demo'] = bool(d['is_demo'])
    if with_events:
        d['events'] = json.loads(d['events'])
    else:
        d.pop('events')
    return d


def count_available(case, field):
    """Legacy zero counts are ambiguous; new imports retain explicit availability."""
    key = 'steps_known' if field == 'step_count' else 'annotation_known'
    return case['metadata'].get(key, case[field] > 0) is True


def get_cases(source='all', status='all', q='', limit=1500):
    clauses, args = [], []
    if source != 'all':
        clauses.append('source=?'); args.append(source)
    if status != 'all':
        clauses.append('outcome=?'); args.append(status)
    if q:
        clauses.append('(task LIKE ? OR agent LIKE ? OR category LIKE ?)')
        args.extend(['%'+q[:80]+'%']*3)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with connection() as db:
        rows = db.execute('SELECT * FROM cases' + where + ' ORDER BY is_demo ASC, issue_count DESC, step_count DESC LIMIT ?',args+[limit]).fetchall()
        return [_to_case(row) for row in rows]


def get_case(cid):
    with connection() as db:
        row = db.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
        return _to_case(row,True) if row else None


def overview(source='all'):
    where = ' WHERE source=?' if source!='all' else ''
    args = [source] if source!='all' else []
    with connection() as db:
        totals = dict(db.execute('''SELECT COUNT(*) AS total,
            SUM(CASE WHEN outcome='solved' THEN 1 ELSE 0 END) AS solved,
            SUM(CASE WHEN outcome='unsolved' OR outcome='failed' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN outcome='unverified' THEN 1 ELSE 0 END) AS unknown,
            AVG(CASE WHEN COALESCE(json_extract(metadata,'$.steps_known'), step_count>0) THEN step_count END) AS avg_steps,
            SUM(issue_count) AS findings,
            SUM(is_demo) AS demo_count
            FROM cases''' + where,args).fetchone())
        by_source = [dict(r) for r in db.execute('SELECT source, COUNT(*) AS count FROM cases'+where+' GROUP BY source ORDER BY count DESC',args)]
        by_agent = [dict(r) for r in db.execute('''SELECT agent,COUNT(*) AS count,
            SUM(CASE WHEN outcome='solved' THEN 1 ELSE 0 END) AS solved,
            SUM(CASE WHEN outcome IN ('unsolved','failed') THEN 1 ELSE 0 END) AS failed,
            ROUND(AVG(CASE WHEN COALESCE(json_extract(metadata,'$.steps_known'), step_count>0) THEN step_count END),1) AS avg_steps FROM cases'''+where+' GROUP BY agent ORDER BY count DESC LIMIT 10',args)]
        by_category = [dict(r) for r in db.execute('SELECT category, COUNT(*) AS count FROM cases'+where+' GROUP BY category ORDER BY count DESC LIMIT 8',args)]
        rows = db.execute('SELECT signals FROM cases'+where,args).fetchall()
    from collections import Counter
    patterns=Counter(s for row in rows for s in set(json.loads(row['signals'])) if s!='No rule-based anomaly found')
    return {'total':totals['total'] or 0, 'solved':totals['solved'] or 0,'failed':totals['failed'] or 0,
        'unknown':totals['unknown'] or 0,'avg_steps':round(totals['avg_steps'] or 0,1),
        'findings':totals['findings'] or 0,'demo_count':totals['demo_count'] or 0,
        'by_source':by_source,'by_agent':by_agent,'by_category':by_category,
        'patterns':[{'name':name,'count':val} for name,val in patterns.most_common(8)]}


def clear_demo():
    with connection() as db:
        result = db.execute('DELETE FROM cases WHERE is_demo=1')
        return result.rowcount


def performance_lab(agent=None, category=None, outcome=None):
    """Analyze all imported benchmark rows, independent of the case-list limit.

    Categories are never pooled for performance or trajectory comparisons.
    Only explicit benchmark solved/unsolved labels enter a success denominator.
    """
    from collections import defaultdict
    from statistics import mean, median

    with connection() as db:
        options = db.execute("SELECT DISTINCT agent, category, outcome FROM cases WHERE source='Tracebench' AND is_demo=0").fetchall()
        clauses = ["source='Tracebench'", 'is_demo=0']
        args = []
        for field, value in [('agent', agent), ('category', category), ('outcome', outcome)]:
            if value is not None:
                clauses.append(field + '=?')
                args.append(value)
        rows = [dict(r) for r in db.execute(
            'SELECT agent,category,outcome,step_count,metadata FROM cases WHERE ' + ' AND '.join(clauses), args)]
        for row in rows:
            row['metadata'] = json.loads(row['metadata'])

    def counts(items):
        solved = sum(r['outcome'] == 'solved' for r in items)
        unsolved = sum(r['outcome'] == 'unsolved' for r in items)
        verified = solved + unsolved
        return dict(total=len(items), solved=solved, unsolved=unsolved,
                    excluded=len(items)-verified, verified=verified,
                    success_rate=round(100*solved/verified, 1) if verified else None)

    def steps(items, label):
        values = [r['step_count'] for r in items if r['outcome'] == label and count_available(r, 'step_count')]
        return dict(count=len(values), mean=round(mean(values), 1) if values else None,
                    median=median(values) if values else None)

    categories = defaultdict(list)
    for row in rows:
        categories[row['category']].append(row)
    results = []
    for name, items in sorted(categories.items()):
        agents = defaultdict(list)
        for row in items:
            agents[row['agent']].append(row)
        results.append(dict(category=name, **counts(items),
                            agents=[dict(agent=a, **counts(group)) for a, group in sorted(agents.items())],
                            steps={label: steps(items, label) for label in ('solved', 'unsolved')}))
    return dict(filters=dict(agent=agent, category=category, outcome=outcome),
                options={field: sorted({r[field] for r in options}) for field in ('agent', 'category', 'outcome')},
                total=len(rows), excluded=sum(r['outcome'] not in ('solved', 'unsolved') for r in rows),
                categories=results)
