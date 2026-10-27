# Public portfolio demo: deployment readiness

**Prepared, not publicly deployed.** Creating a service requires the project owner's approval. Publishing the benchmark demo also requires a defensible dataset permission/license basis. No paid resources are required by the proposed configuration, and no service has been created.

## Recommended hosting

Use a **Render Free Python web service**, one Uvicorn process, with a prepared real-data seed included in the build artifact and a fresh read-only SQLite database created at each startup. This preserves the existing FastAPI/HTML/CSS/JavaScript architecture. No separate database server, frontend rewrite, scheduled job, or paid persistent disk is needed for an immutable benchmark demo.

Verified on 27 October 2026 against the provider's official documentation:

* [Render Free](https://render.com/docs/free): free web services exist, sleep after 15 idle minutes, and can take about a minute to wake. Filesystem changes disappear on restart, redeploy, or spin-down. A workspace receives 750 free instance hours per calendar month. Bandwidth/build quotas also apply; without a payment method, exceeding relevant allowances suspends services/builds instead of providing an unlimited free service. If payment is added, review spend controls and possible overage charges. Free hosting is not an uptime guarantee.
* [Render disks](https://render.com/docs/disks): persistent disks require a paid service. An editable multiuser deployment would need a separate design for persistence and authentication. Do not use the expiring free Postgres tier as a permanent storage workaround.
* [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-overview): the current documentation says creation of Docker/Gradio compute Spaces requires a paid plan. A free static Space cannot run this FastAPI server without an architectural change, so it is not the recommended zero-cost route.

The supplied `render.yaml` is a preparation artifact with `plan: free` and automatic deployment disabled. It does not create resources merely by existing in GitHub. After approval, explicitly verify that Render still offers the Free plan and that account-specific billing requirements are acceptable. Never substitute a paid plan silently.

## Dataset permission is an outstanding launch gate

The [Tracebench dataset card](https://huggingface.co/datasets/Contextbench/Tracebench/blob/main/README.md), [top-level files](https://huggingface.co/datasets/Contextbench/Tracebench/tree/main), and Hub API metadata were checked. No license is declared in the card metadata and no license file was listed. This does **not** establish that redistribution or public display is permitted. Attribution and public download availability are not substitutes for permission. Underlying TerminalBench/SWE-bench terms also need consideration; do not assume a license from either automatically covers Tracebench's derived annotations.

Before publishing, establish applicable license terms or obtain permission covering public display of the derived metadata, keep the evidence, and apply required notices. No author was contacted during this task. `AGENTOPSY_DATA_PERMISSION_REFERENCE` must identify that actual evidence; entering a placeholder or the dataset URL is not permission. The setting is an operator attestation, not an automated legal verification. `public` mode refuses startup without a nonempty reference. Deployment approval from the project owner is a separate requirement.

The real dataset, prepared seed, local databases, Codex logs, and screenshots are excluded from Git. A safe **localhost-only preview** is available while publication permission is unresolved. Do not bind `demo-preview` to a public interface or use it to bypass the publication gate.

## Reproducible seed preparation

Run from the repository directory with the dependencies installed:

```powershell
python -m app.public_demo prepare --manifest C:/path/to/bench_manifest.verified.jsonl --output data/public-demo.json
```

Alternatively, test the fixed public-source download used by the Render build:

```powershell
python -m app.public_demo prepare --download --output data/public-demo.json
```

The command refuses to overwrite an existing output. For a rebuild, choose a new output path or explicitly remove only the old generated seed after inspecting it. The supplied Render build starts from a clean checkout; do not commit a seed file into it.

Preparation reads the **manifest, never the developer's database**, verifies its audited SHA-256, invokes the existing importer, checks uniqueness and the expected outcome totals, and writes only extracted case metadata/stage summaries. Source paths, raw prompts, tool output, commands, and personal Codex cases are not carried over. It includes dataset attribution and the source checksum. Preparation itself grants no publication rights.

Pinned source:

```text
https://huggingface.co/datasets/Contextbench/Tracebench/resolve/main/bench_manifest.verified.jsonl
SHA-256: 5b33978effbeaa966d701160429729eb9631d524305abc870f9aa0d421ef8963
Expected: 1,000 Tracebench runs = 504 solved + 468 unsolved + 28 unverified
Annotations: 595 explicit zeros + 405 positive counts
```

The URL follows upstream `main`, but the checksum is fixed. If upstream bytes change or the download fails, the build fails; it must not substitute another snapshot, the developer DB, or synthetic examples. Review any new snapshot and update tests/research documentation deliberately. Runtime startup requires the prepared seed and performs no network download. The seed is trusted operator-managed build input; this is not a signed dataset attestation.

## Local demo preview

```powershell
$env:AGENTOPSY_MODE = 'demo-preview'
$env:AGENTOPSY_DEMO_SEED = 'data/public-demo.json'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8767 --workers 1 --limit-concurrency 32 --timeout-keep-alive 5
```

On macOS/Linux, prefix the command with `AGENTOPSY_MODE=demo-preview AGENTOPSY_DEMO_SEED=data/public-demo.json`. Do not use Uvicorn's `--reload` on the hosted service. `.python-version` selects the latest Python 3.13 patch on Render, as documented in [Render's Python version settings](https://render.com/docs/python-version).

`local` remains the default for development, with existing SQLite persistence and editable imports. Use `Remove-Item Env:AGENTOPSY_MODE` in PowerShell (or `unset AGENTOPSY_MODE` on Unix) to return to local mode in a shell where preview was enabled. The demo's `AGENTOPSY_DB` is intentionally ignored: startup always selects a fresh temporary database. Existing local databases are neither opened nor overwritten in preview/public mode.

## Startup and persistence behavior

1. Validate the mode and the publication reference for public mode.
2. Load and validate the prepared benchmark seed. Missing, mismatched, duplicate-ID, or mixed-source seeds fail startup; there is no fallback to private or synthetic data.
3. Create and seed an isolated temporary SQLite database, then switch subsequent SQLite connections to URI `mode=ro`.
4. Serve immutable benchmark reads. Reject every non-GET/HEAD/OPTIONS request in demo mode before processing an upload body.
5. Close SQLite connections deterministically. On shutdown remove the temporary demo database; restart reconstructs the same dataset from the build artifact. Normal developer storage is restored in the process context.

This is reproducible data availability, not durable mutable storage. A free-instance disk reset loses no visitor changes because visitors cannot write. The app must run with its normal ASGI lifespan enabled. Use a single process as configured; no public administrative mutation interface is supplied.

## Security review and boundaries

The editable local API is unsuitable as a shared public service: it has no authenticated per-user isolation, imports can overwrite matching IDs, and demo removal deletes cases. Public/preview mode therefore blocks **all write methods**, including `/api/import` and `/api/demo`, and removes upload affordances. Hiding buttons alone is not the control; server middleware and SQLite read-only connections enforce it.

Local uploads remain available. They are processed as bytes, never executed, and now have an 8 MB streaming bound even without `Content-Length`; malformed/negative content lengths are rejected. Existing JSONL schema/line limits and safe Codex extraction remain. This is not a claim that arbitrary uploads are safe for an internet-facing multiuser service. Authentication, per-user data separation, abuse controls, and a broader threat review would be required before enabling that workflow publicly.

Prepared source bytes are pinned; frontend data labels are escaped; static files are confined to the static directory. Responses set MIME-sniffing, referrer, and framing protections. JSON/static responses use gzip when requested for larger payloads. Uvicorn concurrency is bounded at 32; this may return 503 under load instead of accepting unlimited concurrent work. Provider TLS and ingress controls must be checked during an approved deployment. Google Fonts remains the existing optional external font request; analytics do not call remote AI APIs.

FastAPI, Starlette, Uvicorn, and Pydantic were upgraded and pinned. A production requirements audit on 27 October 2026 resolved 14 packages and reported **0 known vulnerabilities**. This is a point-in-time advisory check, not a penetration test or assurance against undiscovered vulnerabilities. Audit again before deployment and periodically afterward. The test client currently emits one upstream httpx deprecation warning; tests still pass.

## Approved deployment procedure — do not execute yet

Only after **both** project-owner deployment approval and dataset publication rights are established:

1. Connect the existing GitHub repository to a new Render **Free Python web service**, or review `render.yaml` via Blueprint setup. This would create a public service, so it must not be done before approval.
2. Confirm the repository root is the directory containing `app/`, `requirements.txt`, and `render.yaml`. Use `.python-version` for Python 3.13. Do not attach a paid disk, database, or other paid resource.
3. Build: `pip install -r requirements.txt && python -m app.public_demo prepare --download --output data/public-demo.json`.
4. Set `AGENTOPSY_MODE=public`, `AGENTOPSY_DEMO_SEED=data/public-demo.json`, and `AGENTOPSY_DATA_PERMISSION_REFERENCE` to the evidence of cleared rights. Do not copy local `.env` files or local SQLite databases.
5. Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 32 --timeout-keep-alive 5`. Health path: `/api/health`. Keep automatic deployments off; future public updates remain deliberate.
6. Verify the host reports healthy, the source attribution is visible, totals are 1,000/504/468/28, private case IDs are absent, uploads/deletion return 403, and all existing read views work over HTTPS. Recheck the same counts after an instance restart. Do not expose stack traces, source manifests, or seed files via static routes.

No Render account resources, custom domains, paid services, or public endpoints have been created or tested here. Hosted cold starts, real ingress limits, billing eligibility, and live uptime cannot be certified from localhost tests.

## Validation and reproducibility

```powershell
python -m pytest -q
# Optional advisory audit tool, installed separately:
python -m pip_audit -r requirements.txt
```

Optional browser tests use the Playwright setup in README:

```powershell
# Editable app at localhost:8766
node tests/browser_research.cjs
node tests/browser_failure.cjs
# Isolated real-data preview at localhost:8767
node tests/browser_demo.cjs
```

`AGENTOPSY_URL` can override each script's URL; `AGENTOPSY_SCREENSHOTS` selects an existing local screenshot output folder. The demo script expects the pinned 1,000-run seed. Python tests use synthetic fixtures and temporary databases, including permission gating, seed integrity, source isolation, SQL read-only enforcement, blocked writes, restart reconstruction, 28-outcome logic through source-fidelity tests, invalid uploads, and existing feature compatibility. No test suite deploys anything.

Local preview measurements (five sequential requests per endpoint, median, uncompressed response bytes) were approximately 27–101 ms across overview, cases, agent performance, Failure Lab, and findings. Payloads ranged from about 1 KB to 671 KB. These are laptop smoke measurements, **not cloud latency or scalability claims**; gzip reduces transfer size for clients that request it. Free-tier CPU, cold starts, and concurrent traffic can behave differently.
