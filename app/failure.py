"""Descriptive failure investigation. No inferred root causes or remote calls."""
from collections import defaultdict
from statistics import mean, median

from .storage import connection, _to_case, count_available as available

SMALL_SAMPLE = 10
NO_SIGNAL = 'No rule-based anomaly found'
PATTERNS = {
    'Unsolved benchmark task': ('outcome', None, 'The benchmark labels the task unsolved. This is the result, not an explanation of failure.'),
    'Annotated incorrect stages': ('annotation', 'stages', 'The manifest reports incorrect stages. It does not identify a causal failure mechanism or provide full tool actions.'),
    'Long trajectory': ('heuristic', None, 'The importer flags runs with at least 100 recorded steps. This threshold is a rule of thumb, not a failure diagnosis.'),
    'Tool error': ('recorded event', 'errors', 'An imported Codex action recorded an error or nonzero exit code. Errors can be recovered from and do not prove task failure.'),
    'Run error': ('recorded event', 'errors', 'A Codex execution error was recorded. Execution failure is distinct from an independently evaluated task outcome.'),
    'Repeated command': ('heuristic', 'adjacent repeats', 'The importer flagged at least two adjacent repeats of identical commands. Repetition can be intentional. Command text is not stored.'),
    'Incomplete trace': ('heuristic', None, 'No completed turn or explicit run failure was recorded. The trace may be partial; task correctness is unknown.'),
}
BINS = [(0, 24, '0–24'), (25, 49, '25–49'), (50, 99, '50–99'),
        (100, 199, '100–199'), (200, None, '200+')]


def verified(case):
    return case['source'] == 'Tracebench' and case['outcome'] in ('solved', 'unsolved')


def evidence_names(case):
    return set(case['signals']) - {NO_SIGNAL}


def length_stats(cases):
    values = [c['step_count'] for c in cases if available(c, 'step_count')]
    return dict(cases=len(cases), count=len(values), missing=len(cases)-len(values),
                mean=round(mean(values), 2) if values else None,
                median=median(values) if values else None,
                small_sample=len(values) < SMALL_SAMPLE)


def category_stats(name, cases):
    labeled = [c for c in cases if verified(c)]
    solved = [c for c in labeled if c['outcome'] == 'solved']
    unsolved = [c for c in labeled if c['outcome'] == 'unsolved']
    annotated = [c for c in labeled if available(c, 'incorrect_stages')]
    return dict(category=name, total=len(cases), verified=len(labeled), solved=len(solved),
                unsolved=len(unsolved), excluded=len(cases)-len(labeled),
                success_rate=round(100*len(solved)/len(labeled), 2) if labeled else None,
                small_sample=len(labeled) < SMALL_SAMPLE,
                length=length_stats(labeled),
                steps={label: length_stats(group) for label, group in [('solved', solved), ('unsolved', unsolved)]},
                annotations=dict(known_cases=len(annotated), missing_cases=len(labeled)-len(annotated),
                                 affected_cases=sum(c['incorrect_stages'] > 0 for c in annotated),
                                 stages=sum(c['incorrect_stages'] for c in annotated)),
                distribution=[dict(label=label, minimum=low, maximum=high,
                                   **{outcome: sum(available(c, 'step_count') and c['step_count'] >= low and
                                                   (high is None or c['step_count'] <= high) for c in group)
                                      for outcome, group in [('solved', solved), ('unsolved', unsolved)]})
                              for low, high, label in BINS])


def failure_lab(agent=None, category=None, outcome=None, min_steps=None, max_steps=None, signal=None):
    with connection() as db:
        all_cases = [_to_case(row) for row in db.execute('SELECT * FROM cases WHERE is_demo=0 ORDER BY category,agent,id')]
    options = {field: sorted({c[field] for c in all_cases}) for field in ('agent', 'category', 'outcome')}
    options['signal'] = sorted({s for c in all_cases for s in evidence_names(c)})
    filters = dict(agent=agent, category=category, outcome=outcome, min_steps=min_steps, max_steps=max_steps, signal=signal)
    cases = [c for c in all_cases if
             (agent is None or c['agent'] == agent) and
             (category is None or c['category'] == category) and
             (outcome is None or c['outcome'] == outcome) and
             (signal is None or signal in evidence_names(c)) and
             (min_steps is None or (available(c, 'step_count') and c['step_count'] >= min_steps)) and
             (max_steps is None or (available(c, 'step_count') and c['step_count'] <= max_steps))]
    groups = defaultdict(list)
    for case in cases:
        groups[case['category']].append(case)
    categories, insights = [], []
    for name, group in sorted(groups.items()):
        stats = category_stats(name, group)
        stats['agents'] = [dict(agent=a, **category_stats(name, [c for c in group if c['agent'] == a]))
                          for a in sorted({c['agent'] for c in group})]
        categories.append(stats)
        s, u = stats['steps']['solved'], stats['steps']['unsolved']
        if s['count'] and u['count']:
            delta = u['median'] - s['median']
            text = (f"In {name}, unsolved runs had a median of {u['median']:g} steps versus "
                    f"{s['median']:g} for solved runs (difference: {delta:+g} steps).")
            insights.append(dict(text=text, category=name, kind='length',
                                 sample_size=s['count']+u['count'], small_sample=min(s['count'], u['count']) < SMALL_SAMPLE,
                                 case_ids=[c['id'] for c in group if verified(c) and available(c, 'step_count')],
                                 limitation='This association does not prove that execution length caused failure. Task difficulty, agent mix, and selective sampling may explain differences.'))
        annotated = [c for c in group if verified(c) and available(c, 'incorrect_stages')]
        if annotated:
            a = stats['annotations']
            insights.append(dict(text=f"In {name}, {a['affected_cases']} of {len(annotated)} runs with known annotation counts have incorrect stages; {a['stages']} incorrect stages were recorded.",
                                 category=name, kind='annotation', sample_size=len(annotated), small_sample=len(annotated) < SMALL_SAMPLE,
                                 case_ids=[c['id'] for c in annotated],
                                 limitation=f"{a['missing_cases']} labeled runs have unknown annotation counts. An incorrect stage is an annotation, not a proven root cause; this is not an annotation accuracy estimate."))
    patterns = []
    for name in sorted({s for c in cases for s in evidence_names(c)}):
        affected = [c for c in cases if name in evidence_names(c)]
        kind, unit, explanation = PATTERNS.get(name, ('recorded signal', None, 'A stored signal label. Its mechanism and occurrence count are not available.'))
        known = []
        if unit:
            for c in affected:
                if name == 'Annotated incorrect stages' and available(c, 'incorrect_stages'):
                    known.append(c['incorrect_stages'])
                elif name in c['metadata'].get('signal_counts', {}):
                    known.append(c['metadata']['signal_counts'][name])
        patterns.append(dict(name=name, kind=kind, explanation=explanation, affected_cases=len(affected),
                             occurrence_unit=unit, measured_occurrences=sum(known) if known else None,
                             unknown_occurrence_cases=len(affected)-len(known) if unit else None,
                             case_ids=[c['id'] for c in affected]))
    return dict(filters=filters, options=options, sample_warning_threshold=SMALL_SAMPLE,
                total=len(cases), verified=sum(verified(c) for c in cases),
                excluded=sum(not verified(c) for c in cases),
                sources={source: sum(c['source'] == source for c in cases) for source in sorted({c['source'] for c in cases})},
                categories=categories, patterns=patterns, insights=insights,
                cases=[dict(id=c['id'], task=c['task'], agent=c['agent'], category=c['category'],
                            source=c['source'], outcome=c['outcome'], signals=sorted(evidence_names(c)),
                            steps=c['step_count'] if available(c, 'step_count') else None,
                            incorrect_stages=c['incorrect_stages'] if available(c, 'incorrect_stages') else None)
                       for c in cases])
