"""Day 5 · Lab 5 · Part 3 — Sequential orchestrator.

Researcher → Analyst → Writer. The slide 39 pattern.

Run: python src/orchestrator.py "<question>"
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from researcher import ask_researcher  # noqa: E402
from analyst import ask_analyst  # noqa: E402
from writer import ask_writer  # noqa: E402

DEFAULT_Q = (
    "How many vacation days does Priya (E-1042) have left, and is "
    "her usage in line with industry norms?"
)


async def run(question: str) -> str:
    t0 = time.perf_counter()
    print(f"USER: {question}\n")

    print("[1/3] Researcher…")
    facts = await ask_researcher(question)
    print(f"{facts}\n")

    print("[2/3] Analyst…")
    analysis = await ask_analyst(question, facts=facts)
    print(f"{analysis}\n")

    print("[3/3] Writer…")
    final = await ask_writer(question, analysis=analysis)
    print(f"{final}\n")

    elapsed = time.perf_counter() - t0
    print(f"=== Capstone complete in {elapsed:.1f}s ===")
    return final


async def _main() -> None:
    q = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_Q
    await run(q)


if __name__ == "__main__":
    asyncio.run(_main())
