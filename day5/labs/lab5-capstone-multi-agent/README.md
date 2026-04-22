# Lab 5 — Capstone: Research → Analyst → Writer multi-agent

> **Time:** ~90 minutes
> **Deck section:** 07 — Hands-on lab (slide 39)
> **Prerequisites:** Labs 1–4 complete · Day 3 eval harness · Day 4
> Foundry agent · Day 4 pipeline

The whole week lands here. You'll build a three-agent Semantic
Kernel system that **composes everything you've built**:

- **Researcher** — gathers facts using the Day 1 HR connector
  (SK plugin from Lab 1) **and** a live web-search tool (Bing API
  with a local mock fallback).
- **Analyst** — reasons over facts using Lab 2's PolicyCompare
  plugin **and** calls the **Day 4 Foundry agent** as a tool for
  complex policy reasoning.
- **Writer** — produces the final answer in Contoso house tone,
  governed by the **Day 5 Lab 4** Entra Agent IDs and quotas.

Orchestrated sequentially (the slide 39 pattern), evaluated with
the **Day 3 golden dataset and harness**, shipped through the
**Day 4 GitHub Actions pipeline** with a new
`deploy-multi-agent-test` job.

If this lab runs end-to-end, every module from the 5-day course
is in production at once.

---

## Architecture

```
   User question
        ↓
   SK Kernel (Azure OpenAI gpt-4o-training)
        ↓
   ┌── Researcher agent
   │      ├─ HRLookupPlugin (Lab 1 — get_vacation_balance, get_hr_policy)
   │      └─ BingSearchPlugin (Lab 5 — real or mock web search)
   │           ↓ FACTS
   ├── Analyst agent
   │      ├─ PolicyComparePlugin (Lab 2)
   │      └─ FoundryDelegateePlugin (Day 4 — invoke Foundry agent as a tool)
   │           ↓ ANALYSIS
   └── Writer agent
          (no tools; prose)
               ↓
          Final answer

All 3 agents → Entra Agent IDs → Agents – Training group → Agent 365 policies

Eval: Day 3 eval_harness.py --backend multi-agent --dataset …
Ship: .github/workflows/agent-promotion.yml → deploy-multi-agent-test job
```

---

## Part 1 — Build the Researcher (25 min)

### 1a. Project scaffold (3 min)

```bash
mkdir -p day5/labs/lab5-capstone-multi-agent/src/plugins
cd day5/labs/lab5-capstone-multi-agent
```

From Lab 1, **copy or symlink** the HRLookup and Summarization
plugins — we'll reuse them.

### 1b. BingSearchPlugin with mock fallback (10 min)

Copy [`src/plugins/bing_search.py`](src/plugins/bing_search.py)
and [`src/plugins/bing_mock.py`](src/plugins/bing_mock.py).

Behavior:

- If `USE_BING_MOCK=true` in env → returns canned HR-relevant
  results from `bing_mock.py`.
- Otherwise → hits `https://api.bing.microsoft.com/v7.0/search` with
  `BING_SEARCH_API_KEY`.

Test:

```bash
USE_BING_MOCK=true python -c \
  "from src.plugins.bing_search import BingSearchPlugin; \
   print(BingSearchPlugin().search('parental leave policy'))"
```

### 1c. Researcher agent (12 min)

Copy [`src/researcher.py`](src/researcher.py).

Same pattern as Lab 2's Researcher but with two plugins bound to
the kernel. Instructions emphasize **calling the right tool for the
kind of question**:

- Employee-specific → `HRLookup.get_vacation_balance`
- Internal policy → `HRLookup.get_hr_policy`
- Industry-benchmark / external context → `BingSearch.search`

Test:

```bash
python src/researcher.py "How does Contoso's parental leave policy compare to the industry average in Europe?"
```

Expected trace: two tool calls, one per source (internal +
external), returned as labelled FACTS.

---

## Part 2 — Build the Analyst with Foundry delegation (15 min)

### 2a. FoundryDelegateePlugin (8 min)

Copy [`src/plugins/foundry_delegatee.py`](src/plugins/foundry_delegatee.py).

This is the interop moment: the SK Analyst calls the **Day 4
Foundry agent** as a tool for complex multi-step reasoning. The
plugin wraps the Foundry `AIProjectClient` in a single
`@kernel_function` that:

1. Creates a thread
2. Posts the question
3. Polls the run to completion (handling `requires_action`)
4. Returns the final message

If you don't have Day 4's Foundry agent, the plugin has a fallback
mode where it calls `gpt-4o-training` directly with a "reasoning"
system prompt. Set `FOUNDRY_AGENT_ID=fallback` to use it.

### 2b. Analyst agent (7 min)

Copy [`src/analyst.py`](src/analyst.py).

Same pattern as Lab 2's Analyst plus the Foundry delegatee.
Instructions route to the right tool:

- Straight comparison → `PolicyCompare.compare_vacation_usage`
- Multi-step reasoning, policy interpretation, counter-factuals
  → `FoundryDelegatee.ask_foundry`

---

## Part 3 — Writer & sequential orchestrator (10 min)

Copy [`src/writer.py`](src/writer.py) and
[`src/orchestrator.py`](src/orchestrator.py).

The Writer is unchanged from Lab 2 — Contoso house tone, 60–80
words, no invented data.

The orchestrator is the slide 39 pattern:

```python
facts     = await researcher.ask(question)
analysis  = await analyst.ask(question, facts=facts)
final     = await writer.ask(question, analysis=analysis)
return final
```

Run end-to-end:

```bash
python src/orchestrator.py "How many vacation days does Priya (E-1042) have left, and is her usage in line with industry norms?"
```

Expected flow: Researcher calls both internal + external sources,
Analyst delegates the comparison to Foundry, Writer produces a
60–80 word answer that cites both Contoso and industry data.

---

## Part 4 — Run the Day 3 eval harness (10 min)

The Day 3 harness is runtime-agnostic. For this lab we ship a tiny
patch adding `--backend multi-agent`.

Apply the patch:

```bash
cp eval_harness_patch.py ../../../day3/labs/lab2-automated-evaluation/eval_harness.py
```

Or just use the pre-patched copy in
[`src/eval_harness.py`](src/eval_harness.py) (self-contained).

Run against the Day 3 golden dataset:

```bash
python src/eval_harness.py \
  --backend multi-agent \
  --dataset ../../../day3/labs/lab2-automated-evaluation/golden-dataset/eval-prompts.jsonl \
  --baseline ../../../day3/labs/lab2-automated-evaluation/golden-dataset/baseline.json \
  --regression-threshold 0.05 \
  --out results-multi-agent.json
```

Expected: 18/20 passing (≥ 85% absolute), regression delta ≤ 5%.
If worse, see *Diagnosis* below.

---

## Part 5 — Ship through the Day 4 pipeline (15 min)

Copy [`pipeline-patch.yaml`](pipeline-patch.yaml) into
`.github/workflows/agent-promotion.yml` — it adds one new job:

```yaml
deploy-multi-agent-test:
  name: Deploy multi-agent system (Test)
  runs-on: ubuntu-latest
  environment: test
  needs: deploy-foundry-test
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: "3.11"}
    - name: Install deps
      run: pip install semantic-kernel azure-ai-projects azure-identity requests
    - name: Run multi-agent eval
      env:
        AZURE_OPENAI_ENDPOINT: ${{ secrets.AZURE_OPENAI_ENDPOINT }}
        AZURE_OPENAI_API_KEY:  ${{ secrets.AZURE_OPENAI_API_KEY }}
        AZURE_OPENAI_DEPLOYMENT: gpt-4o-training
        PROJECT_CONNECTION_STRING: ${{ secrets.PROJECT_CONNECTION_STRING_TEST }}
        USE_BING_MOCK: "true"
      run: |
        python day5/labs/lab5-capstone-multi-agent/src/eval_harness.py \
          --backend multi-agent \
          --dataset golden-dataset/eval-prompts.jsonl \
          --baseline baseline.json \
          --regression-threshold 0.05 \
          --out results-multi-agent-test.json
    - uses: actions/upload-artifact@v4
      with:
        name: eval-results-multi-agent
        path: results-multi-agent-test.json
```

Wire this job so `eval-gate-test` **depends on it** —
`needs: [deploy-foundry-test, deploy-bot-test, deploy-multi-agent-test]`.

Also add two new secrets (Settings → Secrets):

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`

Push the change:

```bash
git add .github/workflows/agent-promotion.yml \
        day5/labs/lab5-capstone-multi-agent/
git commit -m "Day 5 capstone: multi-agent system + pipeline job"
git push
```

Watch Actions → workflow. `deploy-multi-agent-test` should go
green. `eval-gate-test` should still gate on regression.
`promote-to-prod` still requires human approval.

---

## Part 6 — Human-approval promotion (5 min)

Identical to Day 4 Lab 5 Part E. Because your multi-agent system
is inside the same pipeline, the same gate governs it:

1. Green `eval-gate-test` — all three agents cleared.
2. `promote-to-prod` waits for **Review deployments**.
3. Approve — job deploys Studio + Foundry + multi-agent to Prod.
4. Smoke test against 5 prompts returns 5/5.

You now have a governed, evaluated, human-approved multi-agent
system in production. The 5-day journey is complete.

---

## Diagnosis — if the eval regression exceeds 5%

1. Re-run against **each agent individually** — which one regressed?
2. If **Researcher** — Bing-mock vs real Bing results differ.
   Either use real Bing, or rebuild baseline against the mock.
3. If **Analyst** — Foundry delegatee may have different tone than
   pure-SK. Tighten the Foundry agent's instructions to match.
4. If **Writer** — tone drift. Tighten the Writer's system prompt
   (reuse the exact wording from Lab 2 Part 1's Writer).
5. After each fix, re-run the harness. Don't lower the threshold.

---

## Pass criteria

- [ ] Part 1 — Researcher returns labelled FACTS with two sources
      (internal + external) for the industry-benchmark prompt
- [ ] Part 2 — Analyst delegates at least one question to the
      Foundry agent; plugin trace visible in logs
- [ ] Part 3 — `orchestrator.py` produces a 60–80 word Writer
      response for the sample prompt
- [ ] Part 4 — eval harness scores ≥ 85% pass and ≤ 5% regression
- [ ] Part 5 — GitHub workflow `deploy-multi-agent-test` green on
      `main`
- [ ] Part 6 — Prod smoke-test returns 5/5 after human approval

---

## What you just proved (course finale)

You composed your five-day journey into one production system:

| From | Used in capstone | As |
|------|------------------|-----|
| **Day 1** HR connector | Researcher's `HRLookup` plugin | Internal fact source |
| **Day 2** deep reasoning | (available via Foundry delegatee) | Analyst reasoning escape hatch |
| **Day 3** eval harness | `eval_harness.py --backend multi-agent` | Regression gate |
| **Day 3** DLP + Entra | Lab 4 policies applied | Fleet governance |
| **Day 3** budgets | Agent 365 per-agent quotas | Cost guardrail |
| **Day 4** Foundry agent | Analyst's `FoundryDelegatee` plugin | Complex reasoning tool |
| **Day 4** pipeline | `deploy-multi-agent-test` job | CI/CD |
| **Day 5** SK | Researcher, Analyst, Writer | Multi-agent composition |
| **Day 5** Entra Agent ID | Each agent registered | Identity per agent |
| **Day 5** Agent 365 | CA + DLP + audit + quota | Enterprise control plane |

Nothing was wasted. Everything scales. You can build, extend,
operate, integrate, and scale multi-agent systems from here.

**Now go build production-ready agents.**

---

## Reference

- [`test-prompts.md`](test-prompts.md) — full pass-criteria
  checklist
- [`pipeline-patch.yaml`](pipeline-patch.yaml) — YAML snippet to
  merge into Day 4's `.github/workflows/agent-promotion.yml`
- [`architecture.md`](architecture.md) — the diagram above with
  prose walkthrough, useful for your stakeholders
