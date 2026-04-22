# Cognizant Copilot Studio training - Day 4 Lab 5 - promotion pipeline

Live pipeline demonstrating the Day 3/Day 4 story end-to-end:

- **Export** the Copilot Studio solution (`pac solution export`).
- **Deploy** the Foundry agent via `agent-script.py`.
- **Build** the custom-engine bot (Teams Toolkit scaffold).
- **Gate** on the Day 3 eval harness against both surfaces.
- **Promote to Prod** only after gate passes and a human review.

Workflow: `.github/workflows/agent-promotion.yml`
Harness: `eval_harness.py` (Copilot Studio / Direct Line) + `foundry_eval.py` (Foundry Agent Service).
Dataset: `golden-dataset/eval-prompts.jsonl`.
Baselines: `baseline.json`, `foundry-baseline.json`.

See `environment-promotion.md` for the Dev/Test/Prod split.
