#!/usr/bin/env python3
"""
Day 4 Lab 2 — Foundry eval harness.

Runs a representative subset of the Day 3 golden dataset against the
Foundry agent created by agent-script.py, using the new Agent Service
SDK (azure-ai-agents). Emits `foundry-baseline.json` which Lab 5's
promotion gate consumes.

The *shape* mirrors Day 3's harness — per-case graders, pass/fail, a
machine-readable report — but the transport is Foundry threads/runs
instead of Direct Line, and we evaluate a hand-picked subset of cases
whose semantics survive the Copilot Studio → Foundry migration (i.e.
cases whose expectations are about content, not Studio-specific
topic/tool names).

Usage:
    python foundry_eval.py --agent-id <id> --out foundry-baseline.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import importlib.util

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

# agent-script.py uses a hyphen, which Python's import system can't handle
# directly. Load it by path so we can reuse the same tool implementations
# without duplicating the employee/policy seed data.
_spec = importlib.util.spec_from_file_location(
    "agent_script", Path(__file__).resolve().parent / "agent-script.py"
)
_agent_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_agent_mod)  # type: ignore[union-attr]
FUNCTIONS = _agent_mod.FUNCTIONS
get_vacation_balance = _agent_mod.get_vacation_balance
get_hr_policy = _agent_mod.get_hr_policy

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "golden-dataset" / "eval-prompts.jsonl"

# Cases whose semantics are meaningful against a Foundry agent with
# only {get_vacation_balance, get_hr_policy}. We re-phrase some to hit
# the Foundry tool surface rather than Copilot Studio's ListEmployees /
# GetEmployee topics, which Foundry doesn't implement.
REPRESENTATIVE_IDS = {
    "greeting-001",
    "greeting-002",
    "policy-parental-001",
    "timeoff-vacation-001",
    "robust-unknown-id-001",
    "robust-refuse-001",
    "robust-refuse-002",
    "fallback-001",
}

# Extra Foundry-native cases that exercise the agent's real tool surface.
FOUNDRY_EXTRA_CASES = [
    {
        "id": "foundry-vacation-e1357",
        "user_turns": ["How many vacation days does E-1357 have?"],
        "graders": [
            {"type": "content", "match": "regex", "value": r"\b8\b"},
        ],
        "tags": ["foundry", "vacation"],
    },
    {
        "id": "foundry-vacation-e1199",
        "user_turns": ["Daniel Okafor (E-1199) — balance?"],
        "graders": [
            {"type": "content", "match": "regex", "value": r"\b15\b"},
        ],
        "tags": ["foundry", "vacation"],
    },
    {
        "id": "foundry-policy-sick",
        "user_turns": ["What's the sick-leave policy?"],
        "graders": [
            {
                "type": "content",
                "match": "regex",
                "value": r"(?i)\b(medical certificate|3 consecutive days|unlimited)\b",
            },
        ],
        "tags": ["foundry", "policy"],
    },
]


@dataclass
class CaseResult:
    id: str
    ok: bool
    reply: str = ""
    details: list[str] = field(default_factory=list)


def load_jsonl(path: Path) -> list[dict]:
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{line_no}: {e}")
    return cases


def grade_content(spec: dict, reply: str) -> tuple[bool, str]:
    mode = spec.get("match", "substring")
    if mode == "substring":
        v = spec.get("value", "")
        ok = v.lower() in reply.lower()
        return ok, f"substring {v!r}: {ok}"
    if mode == "regex":
        v = spec.get("value", "")
        ok = bool(re.search(v, reply))
        return ok, f"regex /{v}/: {ok}"
    if mode == "llm_judge":
        # Simple heuristic: rely on the LLM's reply itself; if the prompt
        # is answerable from the reply, accept. This matches how Day 3's
        # fallback behaves when OPENAI_API_KEY is unset.
        prompt = spec.get("prompt", "")
        # Common politeness / refusal markers for the privacy cases.
        if "decline" in prompt.lower() or "cannot" in prompt.lower() or "privacy" in prompt.lower():
            ok = bool(
                re.search(r"(?i)(cannot|can't|unable|not able|don't have|privacy|restricted|sorry)", reply)
            )
            return ok, f"judge-heuristic refusal: {ok}"
        if "could not be found" in prompt.lower():
            ok = bool(re.search(r"(?i)(not found|unknown|no record|doesn't exist)", reply))
            return ok, f"judge-heuristic not-found: {ok}"
        if "weather" in prompt.lower():
            ok = bool(re.search(r"(?i)(can't help|cannot|not able|don't know|HR)", reply))
            return ok, f"judge-heuristic fallback: {ok}"
        # Generic: non-empty reply passes.
        ok = bool(reply.strip())
        return ok, f"judge-heuristic generic: {ok}"
    return False, f"unknown content match {mode!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--out", type=Path, default=HERE / "foundry-baseline.json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    endpoint = os.environ["PROJECT_ENDPOINT"]
    client = AgentsClient(endpoint=endpoint, credential=DefaultAzureCredential())

    toolset = ToolSet()
    toolset.add(FunctionTool(functions=FUNCTIONS))
    client.enable_auto_function_calls(toolset)

    # Subset of the Day 3 dataset + Foundry-native additions.
    all_cases = load_jsonl(args.dataset)
    selected = [c for c in all_cases if c["id"] in REPRESENTATIVE_IDS]
    selected.extend(FOUNDRY_EXTRA_CASES)
    print(f"eval: {len(selected)} cases  agent={args.agent_id}")

    results: list[CaseResult] = []
    for c in selected:
        try:
            thread = client.threads.create()
            for turn in c["user_turns"]:
                client.messages.create(thread_id=thread.id, role="user", content=turn)
                run = client.runs.create_and_process(
                    thread_id=thread.id, agent_id=args.agent_id, toolset=toolset
                )
            reply_msg = client.messages.get_last_message_text_by_role(
                thread_id=thread.id, role="assistant"
            )
            reply = reply_msg.text.value if reply_msg else ""

            details = []
            ok_all = True
            for g in c.get("graders", []):
                if g.get("type") != "content":
                    # skip snapshot/flow graders — they assume Studio topics/tools
                    details.append(f"  [skip-grader] {g.get('type')}")
                    continue
                ok, reason = grade_content(g, reply)
                if not ok:
                    ok_all = False
                details.append(f"  [content ] {'OK ' if ok else 'FAIL'} {reason}")
            results.append(CaseResult(c["id"], ok_all, reply, details))
        except Exception as e:
            results.append(CaseResult(c["id"], False, "", [f"  error: {e}"]))

        r = results[-1]
        print(f"  {'PASS' if r.ok else 'FAIL'}  {r.id}")
        if args.verbose or not r.ok:
            for line in r.details:
                print(line)
            if args.verbose:
                print(f"    reply: {r.reply[:140]!r}")

    passed = sum(1 for r in results if r.ok)
    total = len(results)
    rate = passed / total if total else 0.0
    print(f"\nPASS {passed} / FAIL {total - passed}   pass-rate {rate:.1%}")

    report = {
        "backend": "foundry",
        "agent_id": args.agent_id,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": rate,
        "cases": [
            {"id": r.id, "ok": r.ok, "details": r.details, "reply": r.reply}
            for r in results
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"report: {args.out}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
