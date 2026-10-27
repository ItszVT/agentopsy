"""Reproducible descriptive findings from locally imported benchmark records."""
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations

from .failure import category_stats, length_stats, SMALL_SAMPLE
from .storage import connection, _to_case, count_available


def annotation_coverage(cases):
    counts = Counter()
    for c in cases:
        known = count_available(c, 'incorrect_stages')
        status = ('explicit_zero' if known and c['incorrect_stages'] == 0 else
                  'positive' if known else c['metadata'].get('annotation_status', 'legacy_unknown'))
        counts[status] += 1
    return {key: counts[key] for key in ('explicit_zero', 'positive', 'missing', 'invalid', 'legacy_unknown')}


def research_findings(agent=None, category=None):
    # One SQLite read transaction supplies both options and the complete cohort.
    with connection() as db:
        all_cases = [_to_case(row) for row in db.execute(
            "SELECT * FROM cases WHERE source='Tracebench' AND is_demo=0 ORDER BY category,agent,id")]
    cases = [c for c in all_cases if (agent is None or c['agent'] == agent) and
             (category is None or c['category'] == category)]
    labeled = [c for c in cases if c['outcome'] in ('solved', 'unsolved')]
    groups = defaultdict(list)
    for c in labeled:
        groups[c['category']].append(c)
    findings = []

    def add(kind, heading, name, text, groups, limitation):
        ids = [c['id'] for group in groups for c in group]
        findings.append(dict(kind=kind, heading=heading, category=name, text=text,
                             sample_size=len(ids), group_sizes=[len(g) for g in groups],
                             case_ids=ids, limitation=limitation))

    summaries = []
    for name, group in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        summaries.append(category_stats(name, [c for c in cases if c['category'] == name]))
        solved = [c for c in group if c['outcome'] == 'solved']
        unsolved = [c for c in group if c['outcome'] == 'unsolved']
        lengths = [[c for c in g if count_available(c, 'step_count')] for g in (solved, unsolved)]
        if min(map(len, lengths)) >= SMALL_SAMPLE:
            s, u = [length_stats(g) for g in lengths]
            add('length', 'Execution lengths by outcome', name,
                f"Unsolved runs: median {u['median']:g}, mean {u['mean']:g} steps (n={u['count']}). "
                f"Solved runs: median {s['median']:g}, mean {s['mean']:g} steps (n={s['count']}). "
                f"Median difference (unsolved minus solved): {u['median']-s['median']:+g} steps. "
                f"{len(group)-s['count']-u['count']} labeled runs lack known lengths.", lengths,
                'An observed length difference does not establish a cause of failure. Task difficulty, agent/model mix, and sampling can explain it.')
            long_s, long_u = [sum(c['step_count'] >= 100 for c in g) for g in lengths]
            add('recurrence', 'How often runs reach 100 steps', name,
                f"At least 100 steps: {long_u}/{len(lengths[1])} unsolved runs "
                f"({100*long_u/len(lengths[1]):.2f}%) and {long_s}/{len(lengths[0])} solved runs "
                f"({100*long_s/len(lengths[0]):.2f}%). Zero occurrences are shown as zero; the denominator is runs with known lengths.", lengths,
                'The 100-step threshold is an importer heuristic. Its recurrence is a prompt to inspect cases, not a validated failure detector.')
        annotated = [[c for c in g if count_available(c, 'incorrect_stages')] for g in (solved, unsolved)]
        if min(map(len, annotated)) >= SMALL_SAMPLE:
            pos_s, pos_u = [sum(c['incorrect_stages'] > 0 for c in g) for g in annotated]
            stages_s, stages_u = [sum(c['incorrect_stages'] for c in g) for g in annotated]
            add('annotation', 'Incorrect stages and task outcomes', name,
                f"Incorrect stages appear in {pos_s}/{len(annotated[0])} solved runs "
                f"({100*pos_s/len(annotated[0]):.2f}%; {stages_s} stages) and {pos_u}/{len(annotated[1])} unsolved runs "
                f"({100*pos_u/len(annotated[1]):.2f}%; {stages_u} stages). "
                f"{len(group)-len(annotated[0])-len(annotated[1])} labeled runs have unknown annotation counts.", annotated,
                'Only known counts enter these proportions, including explicit zeros. Annotation coverage can bias the comparison; annotations do not prove root causes or evaluation accuracy.')
        by_agent = defaultdict(list)
        for c in group:
            by_agent[c['agent']].append(c)
        eligible = [(a, g) for a, g in sorted(by_agent.items()) if len(g) >= SMALL_SAMPLE]
        for (a, ga), (b, gb) in combinations(eligible, 2):
            sa, sb = [sum(c['outcome'] == 'solved' for c in g) for g in (ga, gb)]
            add('agent', 'Agent outcome shares within one category', name,
                f"{a}: {sa}/{len(ga)} solved ({100*sa/len(ga):.2f}%). "
                f"{b}: {sb}/{len(gb)} solved ({100*sb/len(gb):.2f}%). "
                f"Difference ({b} minus {a}): {100*(sb/len(gb)-sa/len(ga)):+.2f} percentage points.", [ga, gb],
                'These are different run samples, not matched-task trials. Different tasks, models, difficulty, and selective sampling prevent a fair causal ranking of agents.')
    digest_rows = [dict(id=c['id'], agent=c['agent'], category=c['category'], outcome=c['outcome'],
                        steps=c['step_count'] if count_available(c, 'step_count') else None,
                        annotations=c['incorrect_stages'] if count_available(c, 'incorrect_stages') else None)
                   for c in cases]
    fingerprint = hashlib.sha256(json.dumps(digest_rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    solved = sum(c['outcome'] == 'solved' for c in labeled)
    manifests = Counter(c['metadata'].get('manifest_sha256') for c in cases if c['metadata'].get('manifest_sha256'))
    return dict(filters=dict(agent=agent, category=category),
                options={k: sorted({c[k] for c in all_cases}) for k in ('agent', 'category')},
                total=len(cases), solved=solved, unsolved=len(labeled)-solved, verified=len(labeled),
                unverified=len(cases)-len(labeled),
                success_rate=round(100*solved/len(labeled), 2) if labeled else None,
                coverage=annotation_coverage(cases), audited_rows=sum(manifests.values()),
                manifests=[dict(sha256=digest, cases=count) for digest, count in sorted(manifests.items())],
                analysis_sha256=fingerprint, minimum_group_size=SMALL_SAMPLE,
                categories=summaries, findings=findings,
                cases=[dict(id=c['id'], task=c['task'], agent=c['agent'], category=c['category'], outcome=c['outcome']) for c in cases])
