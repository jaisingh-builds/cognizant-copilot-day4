#!/usr/bin/env python3
"""
Copilot Studio agent evaluation harness.

Reads golden-dataset/eval-prompts.jsonl, posts each case against the
agent via Direct Line, and runs the graders declared per case:

  - snapshot  exact match on tool / topic / activity_type / status
  - content   substring | regex | llm_judge (optional OpenAI)
  - flow      sequence of user turns + bot assertions

Usage:
  python eval_harness.py                               # all cases
  python eval_harness.py --limit 3 --verbose           # smoke
  python eval_harness.py --out results/run.json \\
      --baseline golden-dataset/baseline.json \\
      --regression-threshold 0.05

Exits non-zero if:
  - any test case fails AND no baseline is given
  - regression delta is worse than --regression-threshold
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
from typing import Any

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "golden-dataset" / "eval-prompts.jsonl"
DEFAULT_ENDPOINT = "https://directline.botframework.com"


# ---------- Direct Line ----------

def dl_start(endpoint: str, secret: str) -> str:
    r = requests.post(f"{endpoint}/v3/directline/conversations",
                      headers={"Authorization": f"Bearer {secret}"}, timeout=15)
    r.raise_for_status()
    return r.json()["conversationId"]


def dl_post(endpoint: str, secret: str, conv: str, text: str) -> None:
    payload = {"type": "message", "from": {"id": "eval-harness"}, "text": text}
    r = requests.post(
        f"{endpoint}/v3/directline/conversations/{conv}/activities",
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        data=json.dumps(payload), timeout=15,
    )
    r.raise_for_status()


def dl_poll(endpoint: str, secret: str, conv: str, watermark: str | None,
            max_wait: float = 10.0) -> tuple[list[dict], str | None]:
    """Poll until a bot activity arrives or timeout."""
    started = time.time()
    while time.time() - started < max_wait:
        url = f"{endpoint}/v3/directline/conversations/{conv}/activities"
        if watermark:
            url += f"?watermark={watermark}"
        r = requests.get(url, headers={"Authorization": f"Bearer {secret}"}, timeout=15)
        r.raise_for_status()
        body = r.json()
        watermark = body.get("watermark", watermark)
        bot_acts = [a for a in body.get("activities", []) if a.get("from", {}).get("role") == "bot"]
        if bot_acts:
            return bot_acts, watermark
        time.sleep(0.6)
    return [], watermark


# ---------- Extraction ----------

def extract_tool(activities: list[dict]) -> str:
    """Best-effort: Copilot Studio emits `channelData.actions` or chip-like
    entries. This pulls the first tool/topic hint it can find."""
    for a in activities:
        cd = a.get("channelData") or {}
        for key in ("tool", "toolName", "action", "actionName"):
            if isinstance(cd, dict) and cd.get(key):
                return str(cd[key])
        # Also scan entities
        for ent in a.get("entities") or []:
            if ent.get("type") in ("tool", "action") and ent.get("name"):
                return str(ent["name"])
    return ""


def extract_topic(activities: list[dict]) -> str:
    for a in activities:
        cd = a.get("channelData") or {}
        if isinstance(cd, dict) and cd.get("topic"):
            return str(cd["topic"])
    return ""


def extract_text(activities: list[dict]) -> str:
    return "\n".join(a.get("text", "") for a in activities if a.get("text"))


def extract_activity_type(activities: list[dict]) -> str:
    for a in activities:
        atts = a.get("attachments") or []
        if any((att.get("contentType") or "").endswith("adaptive-card.json")
               or "adaptive" in (att.get("contentType") or "") for att in atts):
            return "adaptiveCard"
    return "message" if activities else ""


# ---------- Graders ----------

@dataclass
class GradeResult:
    ok: bool
    reason: str = ""


def grade_snapshot(spec: dict, bot: list[dict]) -> GradeResult:
    field = spec.get("field", "")
    want = spec.get("equals", "")
    got = {
        "tool": extract_tool(bot),
        "topic": extract_topic(bot),
        "activity_type": extract_activity_type(bot),
    }.get(field, "")
    ok = got.lower() == want.lower()
    return GradeResult(ok, f"{field}: expected {want!r}, got {got!r}")


def _llm_judge(spec_prompt: str, bot_text: str) -> GradeResult:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        # Fall back to substring of the first noun-ish word in the prompt
        tokens = [t for t in re.findall(r"[A-Za-z0-9]+", spec_prompt) if len(t) > 3]
        pivot = tokens[0] if tokens else ""
        ok = pivot.lower() in bot_text.lower() if pivot else True
        return GradeResult(ok, f"llm_judge unavailable; substring fallback on {pivot!r}")
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            data=json.dumps({
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content":
                        "You are a strict evaluator. Answer ONLY with YES or NO."},
                    {"role": "user", "content":
                        f"Question: {spec_prompt}\n\nBot reply:\n{bot_text}\n\n"
                        "Does the bot reply satisfy the question? Answer YES or NO."},
                ],
                "temperature": 0,
                "max_tokens": 3,
            }),
            timeout=20,
        )
        r.raise_for_status()
        ans = r.json()["choices"][0]["message"]["content"].strip().upper()
        ok = ans.startswith("Y")
        return GradeResult(ok, f"llm_judge={ans!r}")
    except Exception as e:
        return GradeResult(False, f"llm_judge error: {e}")


def grade_content(spec: dict, bot: list[dict]) -> GradeResult:
    text = extract_text(bot)
    mode = spec.get("match", "substring")
    if mode == "substring":
        v = spec.get("value", "")
        ok = v.lower() in text.lower()
        return GradeResult(ok, f"substring {v!r} in reply: {ok}")
    if mode == "regex":
        v = spec.get("value", "")
        ok = bool(re.search(v, text))
        return GradeResult(ok, f"regex /{v}/ matched: {ok}")
    if mode == "llm_judge":
        return _llm_judge(spec.get("prompt", ""), text)
    return GradeResult(False, f"unknown content match {mode!r}")


def grade_flow(spec: dict, ctx: dict) -> GradeResult:
    """Flow graders need their own Direct Line conversation — the harness
    drives them in `run_flow_case`. Here we just assert `ctx['flow_pass']`
    set by the runner."""
    ok = ctx.get("flow_pass") is True
    return GradeResult(ok, ctx.get("flow_reason", ""))


GRADER_DISPATCH = {
    "snapshot": grade_snapshot,
    "content": grade_content,
    "flow": grade_flow,
}


# ---------- Runner ----------

@dataclass
class CaseResult:
    id: str
    ok: bool
    details: list[str] = field(default_factory=list)


def run_simple_case(endpoint: str, secret: str, case: dict, verbose: bool) -> CaseResult:
    conv = dl_start(endpoint, secret)
    bot: list[dict] = []
    watermark: str | None = None
    for turn in case["user_turns"]:
        dl_post(endpoint, secret, conv, turn)
        acts, watermark = dl_poll(endpoint, secret, conv, watermark)
        bot.extend(acts)
    ctx: dict[str, Any] = {}
    details = []
    ok_all = True
    for g in case.get("graders", []):
        fn = GRADER_DISPATCH.get(g.get("type", ""))
        if not fn:
            ok_all = False
            details.append(f"  unknown grader type {g.get('type')!r}")
            continue
        res = fn(g, bot) if g.get("type") != "flow" else fn(g, ctx)
        if not res.ok:
            ok_all = False
        details.append(f"  [{g.get('type'):<8}] {'OK ' if res.ok else 'FAIL'} {res.reason}")
    if verbose:
        details.append(f"  bot_text: {extract_text(bot)[:240]!r}")
    return CaseResult(case["id"], ok_all, details)


def run_flow_case(endpoint: str, secret: str, case: dict, verbose: bool) -> CaseResult:
    # Find the first flow grader; if multiple, process sequentially.
    details = []
    ok_all = True
    conv = dl_start(endpoint, secret)
    watermark: str | None = None
    for g in case.get("graders", []):
        if g.get("type") != "flow":
            continue
        flow_ok = True
        flow_reason = "ok"
        for step in g.get("turns", []):
            if "user" in step:
                dl_post(endpoint, secret, conv, step["user"])
                acts, watermark = dl_poll(endpoint, secret, conv, watermark)
                continue
            # bot assertion
            acts, watermark = dl_poll(endpoint, secret, conv, watermark, max_wait=2.0)
            text = extract_text(acts)
            if "bot_contains" in step:
                if step["bot_contains"].lower() not in text.lower():
                    flow_ok = False
                    flow_reason = f"expected bot to contain {step['bot_contains']!r}, got {text[:80]!r}"
                    break
            if "expect_topic" in step and extract_topic(acts) != step["expect_topic"]:
                flow_ok = False
                flow_reason = f"expected topic {step['expect_topic']!r}, got {extract_topic(acts)!r}"
                break
            if "bot_activity" in step and extract_activity_type(acts) != step["bot_activity"]:
                flow_ok = False
                flow_reason = f"expected activity {step['bot_activity']!r}, got {extract_activity_type(acts)!r}"
                break
        if not flow_ok:
            ok_all = False
        details.append(f"  [flow    ] {'OK ' if flow_ok else 'FAIL'} {flow_reason}")
    if verbose:
        details.append(f"  (flow case)")
    return CaseResult(case["id"], ok_all, details)


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", help="only cases with this tag", default="")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--baseline", type=Path, default=None)
    ap.add_argument("--regression-threshold", type=float, default=0.05,
                    help="fail if pass-rate drops by more than this fraction")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if requests is None:
        raise SystemExit("pip install requests pyyaml")
    secret = os.environ.get("DIRECT_LINE_SECRET")
    if not secret:
        raise SystemExit("Set DIRECT_LINE_SECRET before running.")
    endpoint = os.environ.get("DIRECT_LINE_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")

    cases = load_jsonl(args.dataset)
    if args.tag:
        cases = [c for c in cases if args.tag in c.get("tags", [])]
    if args.limit > 0:
        cases = cases[: args.limit]

    print(f"eval: {len(cases)} cases  endpoint={endpoint}")
    results: list[CaseResult] = []
    for c in cases:
        is_flow = any(g.get("type") == "flow" for g in c.get("graders", []))
        runner = run_flow_case if is_flow else run_simple_case
        try:
            res = runner(endpoint, secret, c, args.verbose)
        except Exception as e:
            res = CaseResult(c["id"], False, [f"  error: {e}"])
        results.append(res)
        status = "PASS" if res.ok else "FAIL"
        print(f"  {status}  {res.id}")
        if not res.ok or args.verbose:
            for line in res.details:
                print(line)

    passed = sum(1 for r in results if r.ok)
    total = len(results)
    rate = passed / total if total else 0.0
    print(f"\nPASS {passed} / FAIL {total - passed}   pass-rate {rate:.1%}")

    # Write machine-readable report
    report = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": rate,
        "cases": [{"id": r.id, "ok": r.ok, "details": r.details} for r in results],
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2))
        print(f"report: {args.out}")

    # Compare to baseline
    exit_code = 0 if passed == total else 1
    if args.baseline and args.baseline.exists():
        base = json.loads(args.baseline.read_text())
        delta = rate - base.get("pass_rate", 0.0)
        print(f"baseline pass-rate: {base.get('pass_rate', 0):.1%}   delta: {delta:+.1%}")
        if delta < -args.regression_threshold:
            print(f"regression: delta {delta:+.1%} worse than threshold -{args.regression_threshold:.1%}  → FAIL")
            exit_code = 1
        else:
            print("regression gate: OK")
            # Don't auto-pass just because baseline matched; still require all cases to pass if no baseline tolerance intended
            # but allow "some cases fail but within threshold"
            if delta >= -args.regression_threshold:
                exit_code = 0

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        sys.exit(130)
