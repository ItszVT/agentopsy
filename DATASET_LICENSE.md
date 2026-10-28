# Dataset licensing decision and source comparison

Reviewed **28 October 2026**. **Decision: use the official NJU-LINK/CodeTraceBench verified manifest for Agentopsy's derived-metadata public demo under the publisher's explicit MIT declaration.** Keep the attribution, citation, and notices described below. This resolves the previous absence-of-license blocker for that limited scope. It is not a claim of unrestricted rights over every raw trajectory, prompt, source repository, or task asset. Public deployment still requires project-owner approval; no service has been created.

## Primary evidence and original authorship

* Official publisher: [NJU-LINK/CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench), linked from the official [NJU-LINK/CodeTracer project](https://github.com/NJU-LINK/CodeTracer). Both the Hub `cardData.license` value and the dataset card state **MIT**.
* Pinned dataset revision: `aa213b84ffb6690fc37ca15766d6ca174ec36d4d`. [License declaration at that revision](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/blob/aa213b84ffb6690fc37ca15766d6ca174ec36d4d/README.md#license).
* Research authors: Han Li and coauthors, **CodeTracer: Towards Traceable Agent States**, 2026, [arXiv:2604.11641](https://arxiv.org/abs/2604.11641). The dataset card identifies CodeTraceBench as part of that project and credits Nanjing University. Agentopsy does not claim authorship of the dataset or an endorsement by its authors.
* The old [Contextbench/Tracebench mirror](https://huggingface.co/datasets/Contextbench/Tracebench) did not provide an explicit license declaration in the checked card metadata or file listing. Record equality is **not** used to retroactively license that mirror; the demo now downloads the official licensed publication directly.

### Available notices and a documentation inconsistency

The official dataset card's relative `LICENSE` link does not resolve at the pinned dataset revision, and its file listing contains no separate license file or dataset-specific copyright notice. Its explicit MIT declaration is nevertheless present in both the card body and metadata. We preserve that declaration and the citation without inventing a copyright holder.

The associated project's actual license file is [`LICENSE.md`](https://github.com/NJU-LINK/CodeTracer/blob/2d302191dd07e7c0c2da6f7a5e9451c7cbb62d34/LICENSE.md), at checked code revision `2d302191dd07e7c0c2da6f7a5e9451c7cbb62d34`. It contains the MIT terms and an inherited **2025 Kilian A. Lieret and Carlos E. Jimenez** copyright line. That is retained exactly as the available **project-code notice**, not relabeled as a dataset copyright statement or evidence of the research authors' identities. The basis for dataset use is the publisher's **dataset MIT declaration**, not an assumption that the project's software license automatically covers all data.

MIT permits use and redistribution subject to retaining the applicable copyright/permission notices and disclaimer. Agentopsy carries the full available notices in [third_party/NOTICES.txt](third_party/NOTICES.txt), embeds them in prepared seeds, serves them at `/dataset-notices.txt`, and links them visibly beside dataset attribution and the research citation. Public CSV downloads add `dataset_source`, `dataset_license`, and a `license_notice` column; the first data row carries the full notices so a downloaded file retains them. Local CSV format is unchanged. API demo responses also link to the notice endpoint with `rel="license"`.

## Third-party material: scope and exclusions

The manifest describes trajectories originating in TerminalBench and SWE-bench. The checked [SWE-bench repository notice](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/LICENSE) is MIT. The checked [Terminal-Bench repository notice](https://github.com/harbor-framework/terminal-bench-1/blob/d28711d0da2675d0bb1d56de45ae5df6082438a3/LICENSE) is Apache 2.0. Both are retained conservatively in the notices bundle, as separate upstream notices. They do not establish uniform terms for all task assets, third-party source repositories, model-generated content, or issue text. At the checked revisions, both upstream repository root trees list a LICENSE file and no separate NOTICE file. This is not an artifact-by-artifact license audit.

Agentopsy's demo includes only **task identifiers, agent/model/category labels, outcome labels, numeric step and incorrect-stage counts, and numeric stage boundaries**, with derived aggregates. It does **not** redistribute:

* raw prompts or problem statements;
* source code, patches, issue bodies, or task files;
* action/observation content, annotation reasoning, or full step-level records;
* `annotation_relpath`, `source_relpath`, `artifact_path`, or downloaded trajectory archives;
* personal Codex records, private logs, commands, or local file contents.

The official manifest itself contains nested action/observation material in serialized annotation fields. The importer deliberately discards it; no archive is fetched. The new annotation-path field is also discarded. Tests check that representative private strings in all these locations do not survive the projection. Existing local/private import behavior remains separate; a public seed is prepared only from the pinned official manifest, never from SQLite.

This is the scope supported by the publisher's declaration and the reviewed metadata projection. MIT does not override independent third-party rights or warrant that all upstream material is unencumbered. Any future raw trace replay, code/problem display, archive redistribution, or changed dataset revision requires a fresh review. If the official declaration is withdrawn, contradicted, or otherwise no longer reliable, do not publish that dataset: keep the demo localhost-only or use the existing explicitly synthetic examples until a clearly licensed replacement is verified.

## Exact comparison: do not assume identity

Machine-readable evidence: [DATASET_COMPARISON.json](DATASET_COMPARISON.json). Raw manifests remain local and excluded from Git.

| Check | Contextbench snapshot | NJU-LINK official snapshot |
| --- | --- | --- |
| Manifest bytes | 4,987,552 | 5,115,695 |
| SHA-256 | `5b33978effbeaa966d701160429729eb9631d524305abc870f9aa0d421ef8963` | `bd02d3dafa145146567e87f7d55b158ef0dd30043d4a4c2c03e631c2056ff92e` |
| Records / unique trajectory IDs | 1,000 / 1,000 | 1,000 / 1,000 |
| Shared IDs / IDs present in only one source | 1,000 / 0 | 1,000 / 0 |
| Source fields | 18 | 19 |
| Solved / unsolved / null outcome | 504 / 468 / 28 | 504 / 468 / 28 |
| Explicit-zero / positive incorrect-stage counts | 595 / 405 | 595 / 405 |
| Incorrect-stage total | 547 | 547 |

The sole raw field difference is **`annotation_relpath` on all 1,000 official rows**, absent in the mirror snapshot. All shared field values match, including nested serialized annotation contents, stage boundaries, categories, agent/model labels, outcomes, and execution lengths. Row-by-ID normalized comparison finds **zero differences after excluding only the byte-level manifest hash**. Availability/status metadata still participates in that comparison. The files are not byte-identical and are not described as the same publication.

Stable hashed case IDs remain unchanged. The existing database source label `Tracebench` is retained as a compatible import-format family so existing analytics continue working; the public seed's metadata now explicitly identifies `dataset_repo=NJU-LINK/CodeTraceBench`, the pinned revision, MIT, and the research citation. Version-1 mirror seeds are rejected, rather than silently relabeled. Prepared official seeds use `data/public-demo-nju.json` so existing local seeds are not overwritten.

## Recalculated research

All numerical findings, sample memberships, and the normalized analysis SHA-256 remain unchanged:

```text
1162f7d0422a0503bcaa8b8e36c8eeb32330985ff914c77cca228ba9c0aef191
```

This is checked on a newly reconstructed, isolated official-source database. Source provenance changes; the analysis fingerprint intentionally excludes provenance-only fields. The cohort remains 972 explicit outcome labels plus 28 unverified outcomes; all 1,000 annotation counts are known. The 31 eligible observations in The Findings remain descriptive, not causal. [RESEARCH.md](RESEARCH.md) records the calculations and limitations; the CodeTracer paper's own evaluation claims are not claimed as Agentopsy results.

## Reproduce the comparison and demo

```powershell
# Download/check the pinned official source and prepare an isolated metadata seed:
python -m app.public_demo prepare --download --output data/public-demo-nju.json

# With the two local manifests, reproduce the comparison report:
python -m app.public_demo compare --previous C:/path/to/contextbench-verified.jsonl --manifest C:/path/to/nju-verified.jsonl
```

Preparation uses an immutable revision URL and checks the official manifest SHA-256. It refuses to overwrite an existing output. Startup validates source identity, revision, seed version, expected counts, available annotations, provenance, and the notice bundle. Public/preview modes reject all write requests and use SQLite read-only connections after seeding. Restarts recreate the database from the prepared artifact without network access or developer records. A Render deployment is **not** performed by either command; owner approval is still required.

## Research citation

The following citation is supplied by the official dataset card (author names are credited as published):

```bibtex
@article{li2026codetracer,
  title={CodeTracer: Towards Traceable Agent States},
  author={Li, Han and Yao, Yifan and Zhu, Letian and Feng, Rili and Ye, Hongyi and Wang, Jiaming and He, Yancheng and Zou, Pengyu and Zhang, Lehan and Lei, Xinping and Huang, Haoyang and Deng, Ken and Sun, Ming and Zhang, Zhaoxiang and Ye, He and Liu, Jiaheng},
  journal={arXiv preprint arXiv:2604.11641},
  year={2026}
}
```
