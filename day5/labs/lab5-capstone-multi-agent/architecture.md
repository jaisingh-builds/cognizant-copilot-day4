# Capstone architecture walkthrough

Prose version of the diagram in the README. Stakeholder-ready.

---

## One user turn, five days of course

A Contoso employee asks the HR Helper in Teams:

> *"How many vacation days do I have left, and is my usage in line
> with industry norms?"*

The question enters the custom-engine bot (**Day 4 Lab 4**), which
forwards to Copilot Studio (**Day 1**). Copilot Studio's generative
orchestration (**Day 5 Section 06**) decides this needs multi-step
reasoning and calls the capstone multi-agent endpoint.

The multi-agent endpoint is a Semantic Kernel process (**Day 5
Lab 1**) exposing `/ask`. It runs the sequential orchestrator:

### Step 1 — Researcher (~3s)

The Researcher agent (SK `ChatCompletionAgent`, gpt-4o-training)
receives the question. Its instructions route to the right tool:

- For the employee-specific part, it calls `HRLookup.get_vacation_balance`
  (SK plugin wrapping the Day 1 connector) with the employee ID.
- For the industry-norms part, it calls `BingSearch.search` (SK
  plugin wrapping Bing v7 API, or the mock fallback).

It returns labelled `FACTS` — raw, no analysis.

### Step 2 — Analyst (~4s)

The Analyst receives the FACTS and the original question. Its
instructions route to the right tool:

- For straight percentage comparison, it calls
  `PolicyCompare.compare_vacation_usage` (from Lab 2).
- For reasoning about whether Contoso's policy is competitive
  *given* the Bing benchmarks, it calls
  `FoundryDelegatee.ask_foundry` which wraps the **Day 4 Foundry
  Agent Service** agent. Foundry handles multi-step reasoning
  using a thread + run lifecycle the SK Analyst doesn't need to
  care about.

It returns a labelled `ANALYSIS`.

### Step 3 — Writer (~2s)

The Writer receives the ANALYSIS and composes the 60–80 word
Contoso-tone answer. No tools, just prose. The answer flows back
through Copilot Studio to Teams, where the employee reads it.

**Total wallclock: 9–12 seconds.** Token cost: ~$0.03.

---

## Governance applied to every step

Every agent above has an **Entra Agent ID** (**Day 5 Lab 4**) and
is a member of the `Agents – Training` security group. Which means:

- **Access**: each agent can only reach the data sources its RBAC
  allows. The Researcher's Bing key and HR connector scope are
  least-privileged.
- **Policy**: DLP blocks sensitive data from flowing to
  non-Business connectors. Content Safety filters every model
  response. Prompt shields reject injection attempts in the
  incoming user turn.
- **Compliance**: every agent invocation is written to Purview
  Audit with 90-day retention. If the employee's question is
  subject to eDiscovery next year, it's discoverable.
- **Cost**: each agent has a per-agent monthly token quota. The
  Agent 365 dashboard shows real-time spend.

None of this is coded into the agents. It's applied via group
membership — add a sixth agent next month and the same controls
cover it automatically.

---

## How we know it works

The **Day 3 eval harness** runs against the multi-agent endpoint
on every push to `main`. 20 golden prompts, pass-rate gate at 85%,
regression-delta gate at 5% vs baseline. If either fails, the
pipeline blocks promotion to Prod.

The **Day 4 pipeline** promotes from Dev → Test → Prod. The
multi-agent system ships alongside the Copilot Studio solution, the
Foundry agent, and the custom-engine bot — one pipeline, all five
agents.

The **human approval gate** in the pipeline guarantees no
unreviewed change lands in Prod.

---

## What changes if we swap a component?

| Change | Blast radius |
|--------|--------------|
| Replace Researcher's Bing plugin with Google | Redeploy just the Researcher; eval harness catches regressions. |
| Add a fourth agent (Legal reviewer) | Register in Entra, add to group, all policies inherit. Update orchestrator to call it in Group Chat pattern. |
| Move Writer from gpt-4o to a fine-tuned distilled model | Swap the `AZURE_OPENAI_DEPLOYMENT` env var. Rerun eval. Cost drops, tone possibly shifts — fix with tighter prompt. |
| Tighten DLP policy (e.g. block all external web) | Researcher's Bing calls start failing; eval harness catches it; fix by moving the policy question or allowing a scoped web allow-list. |
| Disable one agent (e.g. Foundry is under incident) | Entra Agent ID → Disable. Orchestrator falls through to the PolicyCompare tool for comparisons. Graceful degradation. |

Each of those is a **10-minute change**, not a 10-day project.
That's what the control-plane investment pays for.
