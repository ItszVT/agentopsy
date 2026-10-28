"""Prepare a pinned, derived benchmark seed; never read the developer's SQLite DB."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

from .analyzer import MAX_BYTES, parse_import

SOURCE_REPO = 'NJU-LINK/CodeTraceBench'
SOURCE_REVISION = 'aa213b84ffb6690fc37ca15766d6ca174ec36d4d'
SOURCE_PAGE = 'https://huggingface.co/datasets/'+SOURCE_REPO
SOURCE_URL = SOURCE_PAGE+'/resolve/'+SOURCE_REVISION+'/bench_manifest.verified.jsonl'
SOURCE_SHA256 = 'bd02d3dafa145146567e87f7d55b158ef0dd30043d4a4c2c03e631c2056ff92e'
LICENSE_URL = SOURCE_PAGE+'/blob/'+SOURCE_REVISION+'/README.md#license'
CITATION_URL = 'https://arxiv.org/abs/2604.11641'
NOTICES_PATH = Path(__file__).resolve().parent.parent/'third_party'/'NOTICES.txt'
ATTRIBUTION = 'CodeTraceBench by Han Li et al., NJU-LINK / CodeTracer (2026). Derived benchmark metadata under the published MIT declaration; TerminalBench and SWE-bench origins.'
EXPECTED_COUNTS = {'total': 1000, 'solved': 504, 'unsolved': 468, 'unverified': 28}
SEED_VERSION = 2


def counts(cases):
    return dict(total=len(cases), **{label: sum(c['outcome'] == label for c in cases)
                                   for label in ('solved', 'unsolved', 'unverified')})


def prepare_bytes(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Manifest checksum mismatch. Do not silently substitute a new dataset snapshot.')
    source, cases = parse_import(data)
    if source != 'Tracebench manifest' or counts(cases) != EXPECTED_COUNTS:
        raise ValueError('Benchmark source or outcome counts do not match the audited snapshot.')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate benchmark case IDs.')
    for case in cases:
        case['metadata'].update(dataset_repo=SOURCE_REPO, dataset_revision=SOURCE_REVISION,
                                dataset_license='MIT', dataset_citation=CITATION_URL)
    payload = dict(version=SEED_VERSION, source_url=SOURCE_PAGE, source_sha256=SOURCE_SHA256,
                   source_revision=SOURCE_REVISION, license='MIT', license_url=LICENSE_URL,
                   license_notices=NOTICES_PATH.read_text(encoding='utf-8'),
                   attribution=ATTRIBUTION, citation_url=CITATION_URL, counts=counts(cases), cases=cases)
    return payload


def compare_manifests(previous, candidate):
    """Compare source rows and every normalized field except byte provenance."""
    from .analyzer import read_jsonl
    raw_sets = [read_jsonl(data) for data in (previous, candidate)]
    maps = [{r['traj_id']: r for r in rows} for rows in raw_sets]
    if any(len(rows) != len(mapping) for rows, mapping in zip(raw_sets, maps)):
        raise ValueError('Duplicate source trajectory IDs prevent an unambiguous comparison.')
    old, new = maps
    raw_diffs = Counter()
    for cid in old.keys() & new.keys():
        for field in old[cid].keys() | new[cid].keys():
            if ((field in old[cid]) != (field in new[cid]) or old[cid].get(field) != new[cid].get(field)):
                raw_diffs[field] += 1
    normalized = [parse_import(data)[1] for data in (previous, candidate)]
    normalized_maps = [{c['id']: c for c in cases} for cases in normalized]
    normalized_diffs = Counter()
    for cid in normalized_maps[0].keys() & normalized_maps[1].keys():
        a, b = [mapping[cid] for mapping in normalized_maps]
        for field in a.keys() | b.keys():
            # Availability/status changes must still be detected, unlike file hashes.
            av, bv = a.get(field), b.get(field)
            if field == 'metadata':
                av, bv = [{k:v for k,v in value.items() if k != 'manifest_sha256'} for value in (av,bv)]
            if av != bv:
                normalized_diffs[field] += 1
    schemas = [{field: sorted({type(row[field]).__name__ for row in rows if field in row})
                for field in sorted({k for row in rows for k in row})} for rows in raw_sets]
    return dict(previous_sha256=hashlib.sha256(previous).hexdigest(),
                candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                previous_bytes=len(previous), candidate_bytes=len(candidate),
                previous_rows=len(raw_sets[0]), candidate_rows=len(raw_sets[1]),
                shared_ids=len(old.keys() & new.keys()), previous_only_ids=len(old.keys()-new.keys()),
                candidate_only_ids=len(new.keys()-old.keys()),
                schemas=schemas, raw_differing_fields=dict(sorted(raw_diffs.items())),
                normalized_differing_fields=dict(sorted(normalized_diffs.items())),
                previous_counts=counts(normalized[0]), candidate_counts=counts(normalized[1]))


def load_seed(path):
    seed = json.loads(Path(path).read_text(encoding='utf-8'))
    if (seed.get('version') != SEED_VERSION or seed.get('source_sha256') != SOURCE_SHA256 or
            seed.get('source_url') != SOURCE_PAGE or seed.get('source_revision') != SOURCE_REVISION or
            seed.get('license') != 'MIT' or seed.get('license_url') != LICENSE_URL or
            seed.get('license_notices') != NOTICES_PATH.read_text(encoding='utf-8') or
            seed.get('counts') != EXPECTED_COUNTS or counts(seed.get('cases', [])) != EXPECTED_COUNTS):
        raise ValueError('Demo seed does not match the audited benchmark snapshot.')
    cases = seed['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate demo IDs.')
    # Reject mixed developer databases, Codex cases, and legacy-ambiguous metadata.
    for case in cases:
        if (case['source'] != 'Tracebench' or case['is_demo'] is not False or
                case['metadata'].get('manifest_sha256') != SOURCE_SHA256 or
                case['metadata'].get('dataset_repo') != SOURCE_REPO or
                case['metadata'].get('dataset_revision') != SOURCE_REVISION or
                case['metadata'].get('dataset_license') != 'MIT' or
                case['metadata'].get('annotation_known') is not True or
                case['metadata'].get('steps_known') is not True or
                not case['id'].startswith('tb-')):
            raise ValueError('Demo seed contains unsupported or unaudited records.')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','compare'])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--manifest', type=Path)
    source.add_argument('--download', action='store_true')
    parser.add_argument('--previous', type=Path, help='Previous manifest for the compare command')
    parser.add_argument('--output', type=Path, default=Path('data/public-demo-nju.json'))
    args = parser.parse_args()
    if args.download:
        with urlopen(SOURCE_URL, timeout=60) as response:
            data = response.read(MAX_BYTES+1)
    else:
        data = args.manifest.read_bytes()
    if args.command == 'compare':
        if args.previous is None:
            parser.error('compare requires --previous')
        print(json.dumps(compare_manifests(args.previous.read_bytes(),data),sort_keys=True,indent=2))
        return
    payload = prepare_bytes(data)
    # Never overwrite an existing seed or a database accidentally.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    print(json.dumps(dict(counts=payload['counts'], source_sha256=SOURCE_SHA256,
                          source_revision=SOURCE_REVISION, license='MIT',
                          publication='Metadata-only scope reviewed; owner deployment approval is still required. See DATASET_LICENSE.md.')))


if __name__ == '__main__':
    main()
