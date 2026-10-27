# Agentopsy — an evidence-first agent reliability workbench

**Problem.** AI-agent traces contain execution steps, errors, and outcome labels, but those signals are easy to overinterpret. A completed run is not necessarily a correct result, and a long trajectory does not explain a failure.

**Solution.** Agentopsy turns safe trace metadata into searchable case files, category-specific agent comparisons, a Failure Lab, and a research casebook. Each calculated observation states its sample sizes, limits, and supporting cases. The portfolio demo is prepared as read-only, with real benchmark data available on first visit rather than requiring uploads.

**Stack.** Python, FastAPI, SQLite, plain JavaScript, HTML, and CSS. SQL selects the recorded cohort; Python calculates rates, means, medians, annotation proportions, and exploratory contrasts. No LLM invents findings or explanations. A prepared benchmark seed reconstructs an isolated SQLite demo after hosting restarts.

**Methodology and data reliability.** The audited Tracebench manifest contains 1,000 trajectories. An audit recovered 595 explicit zero annotation counts previously indistinguishable from missing data, and corrected 28 null outcomes that an early importer had mislabeled unsolved. The corrected cohort is 504 solved, 468 unsolved, and 28 unverified. Reimports update stable case IDs without duplicates. Source and analysis fingerprints support reproduction; unknown outcomes and missing counts are never filled by inference.

**Observed findings.** Within software engineering, 223 unsolved runs had median 40 steps, compared with 33 among 378 solved runs. Incorrect-stage annotations appeared in 47.53% and 34.66%, respectively. Within data science, the direction differed: median 34 steps for 17 unsolved runs versus 38 for 19 solved runs. These contrasts motivate investigation; they do not establish causal mechanisms. [Full methodology and case-linked findings](RESEARCH.md).

**Engineering choices.** Public uploads and deletion are disabled server-side, not merely hidden. The prepared seed comes from a checksum-verified manifest, never from the developer's database or personal Codex logs. Public startup requires a reference to cleared dataset publication rights. Render Free is the recommended low-cost hosting option, with ephemeral storage and cold-start tradeoffs documented. No public deployment has been performed, and dataset redistribution permission is still an outstanding launch gate.

**Limits and demonstrated value.** This selectively sampled dataset is observational, agent task sets are not matched, repeated tasks may exist, and the manifest lacks a complete tool timeline. Agentopsy demonstrates a reproducible way to select cases, audit labels, and form hypotheses for follow-up evaluation. It has not measured user adoption, time saved, accuracy improvements, business impact, or production scalability.

**Future improvements.** Obtain explicit dataset publication terms; validate an approved hosted deployment; evaluate hypotheses on matched task sets; add reviewer agreement studies and privacy-preserving step-level evidence only when justified. Authenticated private uploads would require a separate design for isolation, abuse protection, and persistent storage.

Source: [Contextbench/Tracebench](https://huggingface.co/datasets/Contextbench/Tracebench). Setup, verification, rights gating, and the proposed deployment procedure are in [DEPLOYMENT.md](DEPLOYMENT.md).
