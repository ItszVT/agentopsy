"""Prepare a pinned, derived benchmark seed; never read the developer's SQLite DB."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from .analyzer import MAX_BYTES, parse_import

SOURCE_URL = 'https://huggingface.co/datasets/Contextbench/Tracebench/resolve/main/bench_manifest.verified.jsonl'
SOURCE_SHA256 = '5b33978effbeaa966d701160429729eb9631d524305abc870f9aa0d421ef8963'
ATTRIBUTION = 'Contextbench/Tracebench, verified JSONL manifest; selectively sampled TerminalBench and SWE-bench trajectories.'
SOURCE_PAGE = 'https://huggingface.co/datasets/Contextbench/Tracebench'
EXPECTED_COUNTS = {'total': 1000, 'solved': 504, 'unsolved': 468, 'unverified': 28}
SEED_VERSION = 1


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
    payload = dict(version=SEED_VERSION, source_url=SOURCE_PAGE, source_sha256=SOURCE_SHA256,
                   attribution=ATTRIBUTION, counts=counts(cases), cases=cases)
    return payload


def load_seed(path):
    seed = json.loads(Path(path).read_text(encoding='utf-8'))
    if (seed.get('version') != SEED_VERSION or seed.get('source_sha256') != SOURCE_SHA256 or
            seed.get('counts') != EXPECTED_COUNTS or counts(seed.get('cases', [])) != EXPECTED_COUNTS):
        raise ValueError('Demo seed does not match the audited benchmark snapshot.')
    cases = seed['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate demo IDs.')
    # Reject mixed developer databases, Codex cases, and legacy-ambiguous metadata.
    for case in cases:
        if (case['source'] != 'Tracebench' or case['is_demo'] is not False or
                case['metadata'].get('manifest_sha256') != SOURCE_SHA256 or
                case['metadata'].get('annotation_known') is not True or
                case['metadata'].get('steps_known') is not True or
                not case['id'].startswith('tb-')):
            raise ValueError('Demo seed contains unsupported or unaudited records.')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare'])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--manifest', type=Path)
    source.add_argument('--download', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('data/public-demo.json'))
    args = parser.parse_args()
    if args.download:
        with urlopen(SOURCE_URL, timeout=60) as response:
            data = response.read(MAX_BYTES+1)
    else:
        data = args.manifest.read_bytes()
    payload = prepare_bytes(data)
    # Never overwrite an existing seed or a database accidentally.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    print(json.dumps(dict(counts=payload['counts'], source_sha256=SOURCE_SHA256,
                          publication='Not authorized by preparation. Confirm dataset rights and obtain deployment approval.')))


if __name__ == '__main__':
    main()
