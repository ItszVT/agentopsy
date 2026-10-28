# Agentopsy: data reliability and research findings

Agentopsy is a local investigation workbench for agent execution metadata. Its research question is: **which observed differences help an investigator choose runs for closer examination?** It does not claim to discover causal failure mechanisms, improve benchmark accuracy, or deliver measured business impact.

## Dataset and provenance

The current public-demo source is the official [NJU-LINK/CodeTraceBench verified manifest](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench), revision `aa213b84ffb6690fc37ca15766d6ca174ec36d4d`. The publisher declares MIT in the dataset card and metadata. Credit: Han Li et al., [CodeTracer: Towards Traceable Agent States (2026)](https://arxiv.org/abs/2604.11641). The dataset is selectively sampled; its “verified” name does not imply every outcome is non-null.

The official file contains **1,000 records**, **5,115,695 bytes**, and SHA-256:

```text
bd02d3dafa145146567e87f7d55b158ef0dd30043d4a4c2c03e631c2056ff92e
```

The original analysis used the Contextbench/Tracebench mirror (4,987,552 bytes, SHA-256 `5b33978effbeaa966d701160429729eb9631d524305abc870f9aa0d421ef8963`). The sources were compared record by record: all 1,000 IDs, outcomes, categories, agents/models, lengths, stage boundaries, and annotation contents match. The official file adds `annotation_relpath`, which Agentopsy discards. The files are not byte-identical; **all numerical research results and sample memberships remain unchanged**. [Comparison report](DATASET_COMPARISON.json).

The official source is now downloaded directly, never relabeled from a mirror seed. Availability and repository/revision/license provenance are retained, and existing hashed case IDs remain stable. The internal source label `Tracebench` identifies the compatible manifest family; it is not a claim that every local historical import originated from the official publisher. The prepared public seed contains only the official snapshot. Local databases and raw manifests remain outside Git.

[DATASET_LICENSE.md](DATASET_LICENSE.md) records the explicit MIT declaration, dataset authorship, the missing relative dataset LICENSE link, the separately identified inherited project-code copyright notice, and upstream restrictions. Available notices are preserved and linked in the UI and exports. The review covers the derived metadata only, excluding raw prompts, code, problem text, paths and archives. Publication still requires owner approval. See [DEPLOYMENT.md](DEPLOYMENT.md).

Fields used: `traj_id` (hashed into the case ID), `agent`, `category`, `solved`, `step_count`, and `incorrect_error_stage_count`. The official card defines the last field as stages with at least 50% incorrect steps, not individual incorrect actions. Manifest stage boundaries are not full tool-action timelines. Task difficulty, unique-task identity, and agent/model selection are not controlled experimental variables in the comparisons below.

## Reliability investigation and correction

The earliest importer used zero for absent annotation counts and did not retain field availability. The Failure Lab milestone conservatively treated those legacy zeros as unknown. It did not establish that 595 source records were missing annotations.

Auditing the original source file showed:

| Annotation state | Runs |
| --- | ---: |
| Explicit integer zero | 595 |
| Positive integer | 405 |
| Missing or invalid count | 0 |
| Total | 1,000 |

The same audit found **28 `solved: null` values** that the earliest importer had classified as unsolved. The correct source outcomes are:

| Outcome | Before audit | After source reimport |
| --- | ---: | ---: |
| Solved | 504 | 504 |
| Unsolved | 496 | 468 |
| Unverified | 0 | 28 |
| Total Tracebench cases | 1,000 | 1,000 |

All 1,000 trajectory IDs matched. Reimport through the existing `/api/import` endpoint updated those same IDs and inserted **zero** new cases. Only availability/provenance metadata and the 28 incorrectly classified outcomes and their corresponding outcome-signal labels changed. Steps, annotation counts, agents, categories, events, and the separate imported Codex case were preserved. A local SQLite backup was made before the operation. No unknown value was replaced with a fabricated zero.

New imports keep `steps_known` and `annotation_known`, a manifest SHA-256, source row count, and an annotation status (`explicit_zero`, `positive`, `missing`, or `invalid`) in the existing metadata column. Valid counts are nonnegative integers or decimal integer strings within SQLite's signed 64-bit range. Booleans, fractions, negatives, nulls, and invalid strings are not counts. Legacy positive counts remain usable; legacy zero without availability metadata stays unknown until source reimport. Source fingerprints indicate which file was parsed; they are not external attestations of truth.

The import response reports unique IDs, inserted/updated IDs, and duplicate input rows. Existing primary-key upserts make repeat imports idempotent at the case level. If a file repeats an ID, the last row for that ID wins; the response reports the duplicate-row count. Importing a different file can update matching IDs, so retain the source file/checksum for audit and inspect changes before interpreting a changed cohort.

## Methodology

`app/research.py` queries SQLite for **all non-demo Tracebench cases**, without the case-list display limit, and calculates descriptive findings in Python. Agent and category filters define the cohort; every supporting case link belongs to that exact selection. Options remain available from the full imported benchmark sample.

* Outcome denominator: `solved + unsolved`. Unverified outcomes do not enter success rates or outcome comparisons. The corrected sample has 972 labeled runs and an observed solved share of `504 / 972 = 51.85%`. This cross-category number describes the imported sample, not a fair agent ranking.
* Lengths: arithmetic mean and median of known execution-step counts. Missing lengths are excluded and counted separately. Mean values are rounded to two decimals for presentation; medians are computed from the original values.
* Annotation proportions: number of runs with a positive incorrect-stage count divided by runs with known annotation counts, separately by outcome within each category. Explicit zeros stay in the denominator; missing/invalid counts do not. Affected runs and total stages are separate units.
* Recurrence: proportion of known-length runs with at least 100 steps, separately by outcome within category. This is the existing long-trajectory heuristic, not a validated classifier.
* Agent comparisons: solved shares among labeled runs for agent pairs **within one category**. Percentage-point differences are signed as the second agent minus the first; they are descriptive rather than adjusted estimates. Differences use unrounded proportions, so subtracting rounded displayed rates can differ by 0.01 percentage points.
* Eligibility: every compared outcome/agent group needs at least 10 eligible runs. This exploratory cutoff avoids displaying comparisons from extremely small groups; it is not a significance test, power analysis, or confidence interval. Results are ordered by category sample size, then category name; they are not sorted by effect magnitude or favorable agent ranking.
* Reproducibility: an analysis SHA-256 fingerprints the ordered normalized IDs, agent/category, outcome, and available numeric counts. Each response also lists manifest hashes and their selected case counts. Source file and analysis fingerprints serve different purposes.

No LLM, paid service, causal model, p-value, or automated root-cause label participates in these calculations. The visible explanations are deterministic templates containing calculated values. There are multiple exploratory comparisons and no correction for multiple testing; no statistical significance is claimed.

## Observed findings from this snapshot

The unfiltered page calculates 31 eligible observations across categories and comparison types. These examples are snapshots of actual imported data, not hardcoded UI totals. Reimporting or filtering can change them.

### Execution length is associated with outcome differently across categories

Within **software-engineering**, 223 unsolved runs have median **40** and mean **51.37** steps; 378 solved runs have median **33** and mean **35.62** steps. The median difference is **+7 steps**, supported by 601 labeled runs with known lengths. Four additional runs in this category have unverified outcomes and are excluded.

Within **data-science**, 17 unsolved runs have median **34** and mean **36.59** steps; 19 solved runs have median **38** and mean **38.68** steps. Here the median difference is **−4 steps**, supported by 36 labeled runs. This reversal is one reason to keep task categories separate rather than assume every failure follows a longer trajectory.

Neither result establishes causation. Difficulty, task composition, agent/model mix, and sample selection may account for these associations. The data-science sample is much smaller.

### Incorrect-stage annotations occur in solved as well as unsolved runs

Within **software-engineering**, incorrect stages appear in **131/378 solved runs (34.66%; 168 stages)** and **106/223 unsolved runs (47.53%; 157 stages)**. Annotation counts are known for all 601 labeled runs in this comparison. An annotation therefore should not be equated with task failure, and an outcome should not be used as an explanation for itself. The data does not establish whether an annotated issue was recovered from or caused the final outcome.

Across all 1,000 imported Tracebench runs, 405 runs contain 547 incorrect stages. Of these, 8 runs and 13 stages belong to unverified outcomes; those records are excluded from solved-versus-unsolved research comparisons.

### Agent outcome shares differ within the same broad category

Within **software-engineering**, OpenHands solved **234/357 runs (65.55%)**, while SWE-agent solved **80/108 (74.07%)**. The difference is **+8.53 percentage points** for SWE-agent relative to OpenHands, over 465 supporting runs. These are not matched-task experiments. The result cannot establish a generally better agent or model, even though both samples exceed the exploratory size cutoff.

### Long runs are worth investigating, not automatically diagnosing

Within **software-engineering**, **16/223 unsolved runs (7.17%)** reached at least 100 steps, versus **1/378 solved runs (0.26%)**. The page links to all known-length runs used in these denominators. Counts of long runs are small, especially the single solved run; no statistical significance or validated detection accuracy is claimed. Use Failure Lab's length bins to drill into the long runs themselves.

## How an AI development team could use this

An investigator can select a task category and agent, inspect an observed contrast, open its supporting cases, and review the available stage annotations. This can help prioritize trace review, expose missing outcome labels, identify where additional instrumentation is needed, and form hypotheses for a controlled follow-up evaluation. For example, a team could review long solved runs alongside long unsolved runs instead of assuming duration explains failure.

Agentopsy has not measured time saved, product adoption, cost reduction, accuracy gains, or reliability improvements. The value demonstrated here is an auditable investigation workflow and careful separation of evidence from interpretation.

## Remaining limitations

* 28 source outcomes remain null/unverified. They cannot be repaired by inference from other fields or the “verified” split name.
* The verified split is selectively sampled. These rates should not be generalized to all agent work.
* Trajectories are not necessarily unique tasks; repeated or related tasks can violate independence assumptions. No independence-based statistical inference is performed.
* Agent, model, difficulty, task selection, and other confounders are not controlled. Same-category comparisons remain observational.
* Explicit zero is the source's annotation count, not proof that no error occurred. Annotation accuracy and agreement have not been evaluated.
* Manifest metadata cannot reconstruct commands, tool outputs, recoveries, or causal chains. Historical Codex signal occurrence totals remain unknown when the original importer did not retain them. Codex data is excluded from The Findings.
* Local source snapshots and databases are intentionally absent from GitHub; a fresh laptop needs the matching source manifest imported again. The historical mirror revision is not inferred; the official demo revision is explicitly pinned.

## Reproduce the analysis

1. Follow the README's local setup and start the server. Download the [official verified JSONL manifest](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/resolve/aa213b84ffb6690fc37ca15766d6ca174ec36d4d/bench_manifest.verified.jsonl), checking its SHA-256 against the snapshot above. A different checksum means a different source snapshot; do not assume identical results.
2. Use **Import traces** to submit the manifest through the normal importer. Repeat imports update matching IDs, preserving other cases. Verify **The Findings** reports the expected outcome and annotation coverage. The local imported database is the source of the displayed results.
3. Open **The Findings**, select an agent/category, expand methodology and supporting cases, and follow the research-data link for the full calculation response. API examples:

```text
http://127.0.0.1:8765/api/findings
http://127.0.0.1:8765/api/findings?category=software-engineering
http://127.0.0.1:8765/api/findings?category=software-engineering&agent=OpenHands
```

The corrected unfiltered snapshot has analysis SHA-256:

```text
1162f7d0422a0503bcaa8b8e36c8eeb32330985ff914c77cca228ba9c0aef191
```

This fingerprint excludes provenance-only fields and presentation ordering, and does not imply a signed attestation. It changes when the selected normalized records change. The SQL record order used to build it is category, agent, and case ID.

4. Run `python -m pytest -q`. Tests use temporary SQLite databases and synthetic fixtures, including explicit zero, missing/invalid counts, source checksums, repeat/duplicate imports, legacy-null correction, preserved unrelated records, exact medians/means/proportions, sample cutoffs, filter isolation, deterministic fingerprints, and existing endpoint compatibility.
5. With the optional Playwright setup documented in README, run `node tests/browser_research.cjs` and `node tests/browser_failure.cjs` against the running app. They are read-only browser checks for supporting-case navigation, filtering, empty/error states, existing pages, and desktop/tablet/mobile layouts.
