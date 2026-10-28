# Agentopsy

**An investigation desk for AI agent runs.** Agentopsy makes agent execution metadata easier to inspect without inventing success claims or exposing raw prompts. This is a local, free, experimental MVP.

**Portfolio launch status:** a read-only, real-data demo is prepared and tested locally; it is **not publicly deployed**. Render Free is the recommended hosting approach, subject to current account eligibility, cold starts, and usage limits. The licensing blocker is resolved for the derived-metadata scope by using the official NJU-LINK/CodeTraceBench MIT publication, with attribution and upstream notices retained; see [the source comparison and licensing review](DATASET_LICENSE.md). See [deployment readiness and permission gates](DEPLOYMENT.md) before creating any service. [Short portfolio case study](PORTFOLIO.md).

## Run locally (Windows, macOS, Linux)

Install Python 3.10 or later. In the extracted `agentopsy` directory:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

For macOS/Linux activation use `source .venv/bin/activate`.

Open **http://127.0.0.1:8765**. The app starts with **12 synthetic, explicitly labeled example cases** so you can explore every screen immediately. Importing a real file automatically replaces these sample cases. No API key is required.

This default editable mode is for localhost development. For a recruiter-style experience with the audited real sample already loaded, prepare an isolated demo seed and run the localhost-only preview:

```powershell
python -m app.public_demo prepare --download --output data/public-demo-nju.json
$env:AGENTOPSY_MODE = 'demo-preview'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8767 --workers 1
```

The seed command verifies the original source checksum, preserves 504 solved / 468 unsolved / 28 unverified outcomes, and refuses to overwrite existing outputs. It never reads your SQLite database or copies Codex logs. The preview reconstructs a separate temporary SQLite database, disables all writes, and shows benchmark attribution and a first-visit investigation guide. Existing local data remains untouched. `demo-preview` must stay on localhost until deployment is approved. The official source revision, MIT declaration, citation, and notices are verified during seed preparation/startup. Full preparation, restart behavior, cross-platform instructions, and future approved Render setup are in [DEPLOYMENT.md](DEPLOYMENT.md).

## Import real data

### 1. Tracebench benchmark manifest

Download **`bench_manifest.verified.jsonl`** (or `bench_manifest.full.jsonl` when small enough) from [NJU-LINK/CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench/tree/aa213b84ffb6690fc37ca15766d6ca174ec36d4d), then use **Import traces**. The verified split provides 1,000 real benchmark trajectories and their outcomes. In the case of larger files, import a smaller subset. The public dataset is not bundled in this ZIP because it must be attributed and downloaded directly from the source.

**Important:** The manifest offers task outcome labels, step counts, and stage metadata. It does **not** contain full tool action timelines. Agentopsy does not pretend otherwise. The separate benchmark artifact archives are a planned future integration.

### 2. Codex CLI event stream

From a working repository, save the JSONL output using:

```powershell
codex exec --json "explain the repository layout" > run.jsonl
```

Then import `run.jsonl`. Only action categories, exit codes, event counts and safe metadata are retained. Raw commands, file paths, prompts, tool output, and source code are **not saved** in Agentopsy's SQLite database.

A `turn.completed` event indicates **execution completion**, not verified task correctness. Without an independent evaluator, imported Codex tasks are marked `unverified` (or `failed` if an explicit execution error is present).

## Features in version 0.1

* Seven views: investigation overview, searchable case files, pattern lab, trace import, Agent Performance Lab, Failure Lab, The Findings
* SQLite persistence for safe normalized metadata
* Tracebench manifest and Codex JSONL importers
* Outcome integrity: solved / unsolved / execution failed / unverified
* Pattern flags: annotated incorrect stages, long runs, errors, repeated identical commands
* Timeline reconstruction only when a source actually provides stages or events
* CSV export, demo removal, import validation and size limits
* Responsive custom browser UI, no build tooling or paid services

## Running tests

```powershell
pip install pytest httpx
python -m pytest -q
```

Launch checks add seed/source integrity, public write blocking, read-only SQLite, isolated startup/restart behavior, dataset-permission gating, bounded streaming uploads, and existing feature compatibility. Optional browser scripts are `tests/browser_demo.cjs` (preview at port 8767), `tests/browser_research.cjs`, and `tests/browser_failure.cjs` (editable app at port 8766). See [deployment validation instructions](DEPLOYMENT.md#validation-and-reproducibility) for setup and performance/advisory-check limits.

## Agent Performance Lab

Open **Agent Performance Lab** in the sidebar to explore the Tracebench data already imported into SQLite. No additional download or database migration is needed. Demo cases and Codex logs are excluded; an empty lab invites you to import a manifest.

Filter by agent, task category, and outcome, or reset all filters. Each category has its own agent comparison with total runs, solved runs, labeled sample size, success rate, and excluded count. Success rate is `100 × solved / (solved + unsolved)`; unverified and other outcomes never enter that denominator. Missing or non-boolean manifest outcome labels are imported as unverified. A dash means no eligible observations, rather than zero success.

Each category also compares mean and median recorded steps for solved and unsolved runs, with separate sample sizes and a plain-English explanation. Step comparisons exclude all other outcomes. The mean is the average and the median is the middle count. Aggregations use all matching database records, with no case-list display limit. The read-only endpoint is `/api/performance`, with optional `agent`, `category`, and `outcome` query parameters.

Outcome filters also restrict rate denominators: solved-only results show 100%, unsolved-only results show 0%, and unverified-only results have no rate. The view warns when such a filter is active. Clear the outcome filter for a meaningful solved-versus-unsolved comparison.

Comparisons are descriptive, separated by category, and are not a fair leaderboard. Samples count runs, not unique tasks; agents can have different task mixes even in the same category. Small samples and selective benchmark sampling limit conclusions. **Correlation does not prove the cause of failure:** longer trajectories may reflect task difficulty or other differences. No causal failure diagnosis is inferred. Existing imported records are not rewritten; reimport a source manifest to correct any previously misclassified non-boolean outcome labels.

## Failure Pattern Explorer / Failure Lab

Open **Failure Lab** to investigate execution length, unsolved outcomes, and recurring evidence. The page uses the imported SQLite cases; it makes no LLM calls and includes no invented results. Synthetic demo records are excluded. Tracebench manifests support category/agent/outcome comparisons and incorrect-stage annotations. Imported Codex logs can supply recorded execution errors and command-repeat flags; they do not provide independently verified task success. Source counts appear with the active selection.

### Investigating the data

* Filter by agent, category, outcome, evidence signal, and minimum/maximum execution steps. Select filters update immediately; use **Apply step range** for numeric bounds. **Reset all filters** restores the imported sample. Unknown step counts do not match a numeric range.
* **Where agents struggle** shows each category separately: labeled sample size, solved/unsolved counts, success percentage, mean/median steps, known length counts, and known/missing annotation counts. Success is `solved / (solved + unsolved)` using Tracebench labels only. Other sources/outcomes are excluded, including Codex execution failures. An outcome filter restricts the denominator, so solved-only results are trivially 100%.
* **Solved versus unsolved** provides an expandable comparison for each category, including separate means, medians, missing lengths, agent tables, and execution-length distributions. Bins are 0–24, 25–49, 50–99, 100–199, and 200+ steps. Bar labels are raw run counts; both outcomes share a count scale within that category. Unequal sample sizes affect bar heights. Click a bar to apply its category, outcome, and length range to the entire investigation.
* **Evidence pattern register** separates outcomes, annotations, recorded events, and heuristics. Affected cases count each run once per pattern. Recorded occurrence totals are shown separately with their units (stages, errors, adjacent repeats), and with a count of cases whose occurrence totals are unknown. Do not add different units or interpret an outcome such as “Unsolved benchmark task” as a root cause. Pattern explanations expand, and every pattern links to its exact supporting case files.
* **Investigation insights** are Python calculations with category, active filter context, sample size, exact supporting case links, and a statement of limitations. Length insights compare medians only when both outcomes have known lengths. Annotation insights describe only records with known annotation counts. Case links return to Failure Lab with the current filters preserved. The supporting-case list shows 25 rows initially; more rows can be opened without truncating the analysis.

### Missing data and interpretation

The database adds a `metadata` JSON column on startup using an additive, idempotent migration. Existing case IDs, outcomes, events, and counts are retained. New imports preserve whether a step/annotation count was supplied as a valid nonnegative integer, including explicit zero. Missing, negative, boolean, fractional, or invalid values are unknown. Codex imports also retain safe per-signal counts, without storing command text, prompts, hashes, paths, or output.

Earlier importers converted missing numeric fields to zero and did not preserve individual Codex signal counts. For these legacy records, positive numeric counts remain usable; zero counts are conservatively unknown. **A legacy zero annotation count does not prove there were no incorrect stages.** Reimport the original source file to distinguish explicit zeros from missing fields; the same IDs are updated rather than duplicated. Unknown lengths are excluded from distributions, averages, and medians. Missing annotations are excluded from annotation denominators, while known zero annotations remain in them. Dashes mean unknown or not applicable. Historical signal occurrence totals are not reconstructed from the mixed issue count or capped event timelines.

Fewer than 10 labels or known lengths triggers an exploratory small-sample warning, including separate warnings for outcome groups. This threshold is not a confidence interval or statistical significance test. Samples count trajectories, not unique tasks. Task categories are not pooled into a performance ranking; agents can still face different tasks within a category. Correlation does not establish the cause of failure. Neither long runs nor annotated incorrect stages justify an automatic causal diagnosis or recommendation. Selective benchmark sampling limits generalization, and annotation coverage must be considered before interpreting prevalence.

The overview retains its original `findings` API total for compatibility, labeled **Stored issue units** in the UI: this is a historical sum mixing incorrect stages and importer error/heuristic units, not distinct findings. Its flag bars count affected cases once per label; cases can appear in multiple bars. These bars are not expected to sum to the issue total. No business impact or evaluation accuracy has been measured.

### Reproducing and testing

Import a supported JSONL file, start the app as above, and open Failure Lab. The read-only API `/api/failure-lab` returns filters, options, source counts, category/agent summaries, distributions, evidence counts, insights, and exact supporting cases. All calculations use the full matching database selection, without the case-list display limit. For example:

```text
http://127.0.0.1:8765/api/failure-lab?category=software-engineering
http://127.0.0.1:8765/api/failure-lab?agent=OpenHands&min_steps=100&outcome=unsolved
```

Optional parameters are `agent`, `category`, `outcome`, `signal`, `min_steps`, and `max_steps`. Empty filters should be omitted. Numeric bounds are inclusive nonnegative integers; inverted ranges return HTTP 422. Results depend on the locally imported records; SQLite databases and datasets are deliberately excluded from GitHub.

Run `python -m pytest -q` for the full isolated automated suite. Optional read-only browser checks are in `tests/browser_failure.cjs`; they cover filters, chart drill-down, supporting-case return, invalid ranges, empty/error states, existing navigation, and desktop/tablet/mobile widths. With Node.js, Playwright, and Edge available, start the app, then run:

```powershell
$env:AGENTOPSY_URL = 'http://127.0.0.1:8765'
node tests/browser_failure.cjs
```

Install Playwright separately if desired (`npm install --no-save --package-lock=false playwright`), or set `AGENTOPSY_PLAYWRIGHT` to an existing Playwright module path. `AGENTOPSY_BROWSER` selects a Playwright browser channel (default `msedge`); `AGENTOPSY_SCREENSHOTS` optionally names an existing output folder. Browser checks do not import, delete, or modify database records.

## The Findings and data reliability

**The Findings** is an interactive research casebook with agent/category filters, annotation coverage, reproducible source and analysis fingerprints, calculated values, supporting sample sizes, interpretation limits, and exact case links. It compares execution lengths, incorrect-stage proportions, long-run recurrence, and agent outcome shares within task categories. Each comparative group must contain at least 10 eligible runs; this exploratory cutoff is not a significance test. Calculations run in Python over SQLite records without a model API or invented conclusions.

The original manifest audit resolved all **595 ambiguous legacy annotation counts as explicit source zeros**. It also corrected **28 null outcomes previously misclassified as unsolved**: the audited snapshot has 504 solved, 468 unsolved, and 28 unverified Tracebench runs, retaining all 1,000 IDs and the separate Codex case. Outcomes now match the source rather than preserving an incorrect historical total. Reimporting updates existing IDs rather than duplicating cases; the import response reports inserted, updated, and duplicate-row counts. Missing and invalid annotations remain unknown.

See [RESEARCH.md](RESEARCH.md) for the dataset checksum, source attribution, before/after reliability audit, methodology, actual findings, limitations, recruiter-facing project context, and step-by-step reproduction. Source manifests and SQLite databases stay local and are not bundled in GitHub. On another laptop, import the matching manifest to reproduce the data; the code alone does not restore local cases.

Read-only research API: `/api/findings`, with optional `agent` and `category` parameters. For example, `/api/findings?category=software-engineering`. With the same optional browser setup described above, run `node tests/browser_research.cjs` for the new page's browser checks. Run `python -m pytest -q` for the full automated suite.

## How to evaluate it honestly

Compare extracted metadata to source manifests and Codex event streams. Mark heuristics as **signals**, not ground truth root causes. Do not directly rank agent models with datasets that differ in tasks, difficulty, or sample selection. Tracebench's `verified` subset is selectively sampled, so it is not a representative general use benchmark.

## Privacy and limitations

This is a local development tool, not a hardened hosted multiuser service. Run on `127.0.0.1`, not a public server. Imported JSONL is processed in memory and only derived metadata is stored. Input is limited to 8 MB and 5,000 lines. CSV includes derived case metadata. The tool does not execute commands from traces and does not make remote model calls. Avoid uploading private traces to public websites. Review imports for secrets before sharing files with anyone else.

The demo dashboard contains synthetic examples until you import real data. Synthetic counts are not validated performance results. No causal analysis, auto remediation, raw replay of artifact archives, persistent authentication, or API billing is included in this MVP.

## Project structure

```
agentopsy/
  app/
    analyzer.py          # source parsing and flag detection
    storage.py           # SQLite persistence and aggregations
    failure.py           # failure comparisons, evidence counts and insights
    demo.py              # explicitly synthetic demonstration cases
    main.py              # FastAPI routes
    static/              # hand built web interface
  data/                  # local SQLite database created at first launch
  samples/               # safe Codex-style synthetic test log
  tests/                 # unit and API tests
  requirements.txt
```

## Next milestones

1. Compare pattern frequencies in an actual Tracebench split with attribution and sample context.
2. Import safe step-level artifact summaries for verified deep timeline investigations.
3. Add independently labeled failure reason evaluation and reviewer agreement checks.
4. Add user research, onboarding measurements, and feedback instrumentation for the product and growth case study.

## Data and references

* [Official CodeTraceBench dataset (MIT)](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench)
* [CodeTracer paper and dataset citation](https://arxiv.org/abs/2604.11641)
* [Dataset licensing review and third-party notices](DATASET_LICENSE.md)
* [Official Codex JSONL documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
* [Hugging Face trace privacy guidance](https://huggingface.co/docs/hub/agent-traces)
