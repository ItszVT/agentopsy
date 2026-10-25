# Agentopsy: developer handoff

This is the running MVP, not an empty scaffold. Preserve the current interface, evidence integrity, case file flow, local privacy protections, and tested endpoints when extending it.

## Product goal

Agentopsy is an approachable investigation workbench for AI agent execution reliability. The user selects a run and sees observed steps, verified outcomes where present, and hypotheses that warrant further investigation. The product should be visually memorable but analytically trustworthy.

## Nonnegotiable rules

1. Never equate `turn.completed` with task success.
2. Never invent actual per-step events when only Tracebench manifest stages are provided.
3. Never store or display raw sensitive prompts, shell command text, source code, tool outputs, file paths, API credentials, or unsanitized input strings from Codex logs.
4. Do not call external LLM APIs or upload logs without explicit informed user consent.
5. Signals from heuristics are not causal explanations, and sampled benchmark agents are not a fair leaderboard.
6. Keep run locally on Windows, free of paid services and keys.
7. Add tests for any new parsing format or evidence claim.

## Immediate Codex task

> Inspect the existing Agentopsy FastAPI and browser code. Run all tests and run the website locally. Without changing the current visual design, add a dedicated import validation report and an expanded benchmark analysis comparing correct vs incorrect stage frequency across task categories, with accurate denominators, statistical context, and citations to Tracebench fields. Add tests. Keep all local privacy rules. Do not push to GitHub automatically. Show changes and test results before any git commit.

## Longer term

* Read separately hosted Tracebench trajectory archives safely and add verified tool timeline reconstruction.
* Build precision and recall evaluation sets for heuristic failure flagging.
* Add optional local annotation UI (reviewers manually mark causes and evidence).
* Research product onboarding and measure task completion rate with consenting testers.
* Add CI and reproducible public dataset snapshots with source attribution.
