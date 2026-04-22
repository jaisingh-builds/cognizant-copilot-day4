# Environment promotion — model & rules

The three-env model that the pipeline enforces.

---

## The three environments

### Dev

**Purpose:** where humans build. Where you've been working all week.

- Copilot Studio env: `Developer` (from Day 1 setup)
- Foundry project: `proj-<your-initials>` (Lab 1)
- Bot env: `teamsapp --env dev` (local or a dev Azure resource group)
- DLP policy: training policy (Day 3) — permissive
- Who edits: the agent owner + trusted reviewer

**Data:** mock / sample. No real employee records.

### Test

**Purpose:** continuous integration. Every push lands here.

- Copilot Studio env: a second env named `Test` (Power Platform
  admin creates)
- Foundry project: `proj-test` in the same training hub
- Bot env: `teamsapp --env test`, Azure resource group
  `rg-agents-test`
- DLP policy: mirrors Prod — strict
- Who edits: **the pipeline only**. No human changes.

**Data:** anonymized real data OR high-fidelity synthetic. Enough
to catch regressions the mock data misses.

### Prod

**Purpose:** real users.

- Copilot Studio env: `Production` (separate from dev)
- Foundry project: `proj-prod`, ideally in a locked-down hub with
  BYO networking
- Bot env: `teamsapp --env prod`, Azure resource group
  `rg-agents-prod` with Private Link to Foundry
- DLP policy: Prod policy, strict
- Who edits: **the pipeline only**, with human approval gate

**Data:** real. Governed by your org's data classification.

---

## What moves across environments

| Thing | Dev | Test | Prod | How it moves |
|---|---|---|---|---|
| Copilot Studio solution | Owner builds | Imported | Imported | `pac solution export/import` |
| Topic definitions | Edited | Read-only | Read-only | Inside the solution zip |
| Custom connector | Edited | Redeployed | Redeployed | Inside the solution zip |
| Foundry agent definition | Edited | Re-created | Re-created | `agent-script.py` idempotent by name |
| Model deployment | Shared training | `gpt-4o-test` | `gpt-4o-prod` | IaC (Bicep/Terraform) |
| Bot code | Edited | Deployed | Deployed | `teamsapp deploy` |
| Golden dataset | Evolved | Read-only | Read-only | Git |
| Baseline snapshot | Owner re-baselines | Compared | Compared | Git |

---

## Promotion gates

### Dev → Test

- Push to `main` triggers pipeline.
- **No human gate.** Test should always reflect `main`.

### Test → Prod

Three gates stacked:

1. **Automated eval.** Regression-delta ≤ 5% vs baseline, ≥ 85%
   absolute pass rate.
2. **Human approval.** A named reviewer clicks "Approve" on the
   GitHub Environment rule.
3. **Change-management ticket** (optional, for regulated orgs).
   Pipeline annotates the deployment with the ticket ID.

If any gate fails, Prod is not touched.

---

## Rollback strategy

### Copilot Studio

- Keep last N solution zips as GitHub Releases.
- Rollback = `pac solution import --path <prev-zip>`.
- Time: ~2 minutes.

### Foundry agent

- Foundry doesn't version agents natively — you manage this in git.
- `agent-script.py` is idempotent by agent name; revert the script,
  re-run, agent is replaced.
- Time: ~1 minute.

### Custom-engine bot

- `teamsapp deploy --env prod` with the previous commit SHA.
- Keep last 5 deploys available in App Service deployment slots for
  instant swap-back.
- Time: < 30 seconds (slot swap) / ~5 minutes (full redeploy).

### Data

Don't roll back **data** alongside the code. Use feature flags / API
versions to handle schema changes forward-only.

---

## Observability across environments

Each env has its own:

- Analytics dashboard (Day 3 Lab 1 — filter by env)
- Azure Cost Management budget (Day 3 Lab 5 — one budget per env)
- Entra Agent ID (Day 3 Lab 4 — one per agent per env)

The pipeline posts a **deployment summary** to Teams after each
promotion — what moved, what the eval said, who approved.

---

## Anti-patterns to avoid

- **"Just fix it in Test"** — no human edits in Test.
- **Shared model deployment across envs** — breaks quota isolation;
  breaks audit; breaks blast-radius analysis.
- **Skipping the eval gate "because this change is small"** — then
  you don't have a process, you have a habit.
- **Pointing Test DLP policy at Dev's permissive settings** — tests
  pass in Test, production fails.
- **No rollback rehearsed** — rollback-by-panic takes 10x longer.
  Rehearse once a quarter.

---

## The governance tie-in

Every env needs all three Day 3 governance layers applied:

| Layer | Dev | Test | Prod |
|---|---|---|---|
| **Data** (DLP) | Training policy | Prod-mirror policy | Prod policy |
| **Identity** (Entra Agent ID) | Training group | Test group | Prod access group |
| **Action** (moderation, approvals) | High | High | High |

The pipeline doesn't set these — the tenant admin does, once, per
env. The pipeline **deploys into** them.
