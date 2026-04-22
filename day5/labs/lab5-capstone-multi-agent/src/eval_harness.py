"""Day 5 · Lab 5 · Part 4 — eval harness extended to multi-agent.

The Day 3 harness is runtime-agnostic. This version adds
--backend multi-agent which routes to the capstone orchestrator.
Other backends ('studio', 'foundry') delegate to the Day 3/4
implementations if you wire them up.

Compatible CLI with Day 3 / Day 4:
  python eval_harness.py \\
    --backend multi-agent \\
    --dataset <path-to-eval-prompts.jsonl> \\
    --baseline <path-to-baseline.json> \\
    --regression-threshold 0.05 \\
    --out <path-to-results.json>
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orchestrator import run as run_multi_agent  # noqa: E402


def load_dataset(path: str) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def load_baseline(path: str | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    with open(path) as f:
        return json.load(f)


def matches(reply: str, must_contain: list[str]) -> tuple[bool, list[str]]:
    lower = reply.lower()
    missing = [kw for kw in must_contain if kw.lower() not in lower]
    return (not missing), missing


async def invoke_multi_agent(prompt: str) -> str:
    # orchestrator.run prints to stdout AND returns the final answer;
    # we only want the final writer output for eval.
    return await run_multi_agent(prompt)


async def invoke(backend: str, prompt: str) -> str:
    if backend == "multi-agent":
        return await invoke_multi_agent(prompt)
    raise ValueError(
        f"Backend '{backend}' not wired in this capstone sample. "
        "For 'studio' / 'foundry', use the Day 3 / Day 4 harnesses."
    )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=["multi-agent"])
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--baseline", default=None)
    ap.add_argument(
        "--regression-threshold", type=float, default=0.05
    )
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    dataset = load_dataset(args.dataset)
    if args.limit:
        dataset = dataset[: args.limit]
    baseline = load_baseline(args.baseline)

    results = []
    passed = 0
    t0 = time.perf_counter()
    for i, case in enumerate(dataset, 1):
        prompt = case["prompt"]
        must_contain = case.get("must_contain", [])
        must_any = case.get("must_contain_any", [])
        try:
            reply = await invoke(args.backend, prompt)
            if must_any:
                lower = reply.lower()
                ok = any(k.lower() in lower for k in must_any)
                missing = [] if ok else must_any
            else:
                ok, missing = matches(reply, must_contain)
            status = "pass" if ok else "fail"
        except Exception as exc:  # noqa: BLE001
            reply = f"ERROR: {exc}"
            ok, missing, status = False, must_contain, "error"
        if ok:
            passed += 1
        marker = {"pass": "\u2713", "fail": "\u2717", "error": "!"}[status]
        print(f"[{marker}] {i}/{len(dataset)} {prompt[:60]}")
        if not ok:
            print(f"     missing: {missing}")
        results.append(
            {
                "id": case.get("id", f"case-{i}"),
                "prompt": prompt,
                "reply": reply,
                "must_contain": must_contain,
                "missing": missing,
                "status": status,
            }
        )
    elapsed = time.perf_counter() - t0

    pass_rate = passed / len(dataset) if dataset else 0.0
    baseline_rate = baseline.get("pass_rate", pass_rate)
    regression = max(0.0, baseline_rate - pass_rate)
    summary = {
        "backend": args.backend,
        "total": len(dataset),
        "passed": passed,
        "pass_rate": pass_rate,
        "baseline_rate": baseline_rate,
        "regression_delta": regression,
        "regression_threshold": args.regression_threshold,
        "elapsed_sec": elapsed,
        "results": results,
    }
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)

    print(
        f"\n=== {passed}/{len(dataset)} passed "
        f"(pass rate {pass_rate:.1%}, baseline {baseline_rate:.1%}, "
        f"regression {regression:.1%}) in {elapsed:.1f}s ==="
    )
    if pass_rate < 0.85:
        print("FAIL: absolute pass rate < 85%")
        return 1
    if regression > args.regression_threshold:
        print(
            f"FAIL: regression {regression:.1%} > threshold "
            f"{args.regression_threshold:.1%}"
        )
        return 1
    print("PASS: gates cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
