# Lab 5 — Test prompts & pass criteria

The capstone is end-to-end; the checks span orchestrator, eval
harness, and pipeline.

---

## Part 1–3 — Orchestrator

Run: `python src/orchestrator.py "<prompt>"`

### Prompt A — Internal + external

`"How does Contoso's parental leave policy compare to the industry average in Europe?"`

| # | Check | Pass |
|---|-------|------|
| 1 | Researcher calls both `HRLookup.get_hr_policy("leave")` and `BingSearch.search(...)` | Yes |
| 2 | Analyst calls `FoundryDelegatee.ask_foundry` with both the Contoso and industry facts | Yes |
| 3 | Writer reply is 60–80 words | Yes |
| 4 | Writer reply mentions both Contoso's policy and the EU/industry benchmark | Yes |
| 5 | Writer reply contains no bullet points | Yes |

### Prompt B — Employee-specific with context

`"How many vacation days does Priya (E-1042) have left, and is her usage in line with industry norms?"`

| # | Check | Pass |
|---|-------|------|
| 6 | Researcher calls `get_vacation_balance("E-1042")` and `BingSearch.search(...)` | Yes |
| 7 | Analyst calls `PolicyCompare.compare_vacation_usage(12.5, 7.5, 20)` | Yes |
| 8 | Writer reply names Priya, cites 12.5 days remaining, and includes an industry comparison | Yes |

### Prompt C — Out-of-scope (negative test)

`"What's the weather in Paris?"`

| # | Check | Pass |
|---|-------|------|
| 9 | Researcher does NOT call the HR plugin (no employee data involved) | Yes |
| 10 | Final reply is a polite refusal / redirect to HR-only scope | Yes |

---

## Part 4 — Eval harness

Run:

```bash
python src/eval_harness.py \
  --backend multi-agent \
  --dataset ../../../day3/labs/lab2-automated-evaluation/golden-dataset/eval-prompts.jsonl \
  --baseline ../../../day3/labs/lab2-automated-evaluation/golden-dataset/baseline.json \
  --regression-threshold 0.05 \
  --out results-multi-agent.json
```

| # | Check | Pass |
|---|-------|------|
| 11 | Script exits 0 | Yes |
| 12 | Absolute pass rate ≥ 85% | Yes |
| 13 | Regression delta ≤ 5% vs baseline | Yes |
| 14 | `results-multi-agent.json` contains per-case results with `status` field | Yes |

---

## Part 5 — Pipeline

| # | Check | Pass |
|---|-------|------|
| 15 | New job `deploy-multi-agent-test` appears in GitHub Actions run | Yes |
| 16 | Job completes green on a clean push | Yes |
| 17 | `eval-gate-test` now depends on `deploy-multi-agent-test` | Yes |
| 18 | Artifact `eval-results-multi-agent` is downloadable | Yes |

---

## Part 6 — Human approval

| # | Check | Pass |
|---|-------|------|
| 19 | `promote-to-prod` waits for **Review deployments** | Yes |
| 20 | Approving runs the Prod smoke test | Yes |
| 21 | Prod smoke returns 5/5 passing | Yes |

---

## Pass criteria

- [ ] Part 1–3: 10/10 orchestrator checks
- [ ] Part 4: 4/4 eval-harness checks
- [ ] Part 5: 4/4 pipeline checks
- [ ] Part 6: 3/3 human-approval checks

**Total: 21 checks. If all pass, the five-day course landed.**

If any fail, see [`../../TROUBLESHOOTING.md`](../../TROUBLESHOOTING.md)
→ *Lab 5*.
