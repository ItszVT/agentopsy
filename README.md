# Agentopsy

**An investigation desk for AI agent runs.** Agentopsy makes agent execution metadata easier to inspect without inventing success claims or exposing raw prompts. This is a local, free, experimental MVP.

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

## Import real data

### 1. Tracebench benchmark manifest

Download **`bench_manifest.verified.jsonl`** (or `bench_manifest.full.jsonl` when small enough) from [Contextbench/Tracebench](https://huggingface.co/datasets/Contextbench/Tracebench/tree/main), then use **Import traces**. The verified split provides 1,000 real benchmark trajectories and their outcomes. In the case of larger files, import a smaller subset. The public dataset is not bundled in this ZIP because it must be attributed and downloaded directly from the source.

**Important:** The manifest offers task outcome labels, step counts, and stage metadata. It does **not** contain full tool action timelines. Agentopsy does not pretend otherwise. The separate benchmark artifact archives are a planned future integration.

### 2. Codex CLI event stream

From a working repository, save the JSONL output using:

```powershell
codex exec --json "explain the repository layout" > run.jsonl
```

Then import `run.jsonl`. Only action categories, exit codes, event counts and safe metadata are retained. Raw commands, file paths, prompts, tool output, and source code are **not saved** in Agentopsy's SQLite database.

A `turn.completed` event indicates **execution completion**, not verified task correctness. Without an independent evaluator, imported Codex tasks are marked `unverified` (or `failed` if an explicit execution error is present).

## Features in version 0.1

* Five views: investigation overview, searchable case files, pattern lab, trace import, Agent Performance Lab
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

## Agent Performance Lab

Open **Agent Performance Lab** in the sidebar to explore the Tracebench data already imported into SQLite. No additional download or database migration is needed. Demo cases and Codex logs are excluded; an empty lab invites you to import a manifest.

Filter by agent, task category, and outcome, or reset all filters. Each category has its own agent comparison with total runs, solved runs, labeled sample size, success rate, and excluded count. Success rate is `100 × solved / (solved + unsolved)`; unverified and other outcomes never enter that denominator. Missing or non-boolean manifest outcome labels are imported as unverified. A dash means no eligible observations, rather than zero success.

Each category also compares mean and median recorded steps for solved and unsolved runs, with separate sample sizes and a plain-English explanation. Step comparisons exclude all other outcomes. The mean is the average and the median is the middle count. Aggregations use all matching database records, with no case-list display limit. The read-only endpoint is `/api/performance`, with optional `agent`, `category`, and `outcome` query parameters.

Outcome filters also restrict rate denominators: solved-only results show 100%, unsolved-only results show 0%, and unverified-only results have no rate. The view warns when such a filter is active. Clear the outcome filter for a meaningful solved-versus-unsolved comparison.

Comparisons are descriptive, separated by category, and are not a fair leaderboard. Samples count runs, not unique tasks; agents can have different task mixes even in the same category. Small samples and selective benchmark sampling limit conclusions. **Correlation does not prove the cause of failure:** longer trajectories may reflect task difficulty or other differences. No causal failure diagnosis is inferred. Existing imported records are not rewritten; reimport a source manifest to correct any previously misclassified non-boolean outcome labels.

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

* [Tracebench dataset](https://huggingface.co/datasets/Contextbench/Tracebench)
* [Official Codex JSONL documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
* [Hugging Face trace privacy guidance](https://huggingface.co/docs/hub/agent-traces)
