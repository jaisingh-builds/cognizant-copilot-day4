"""HTTP service wrapping the Day 5 capstone multi-agent orchestrator.

POST /ask
  body: {"question": "..."}
  resp: {"answer": "...", "elapsed_sec": 12.3}

GET /health
  resp: {"status": "ok"}
"""
import os
import sys
import time

from fastapi import FastAPI
from pydantic import BaseModel

# Reach into ../src for the orchestrator
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
from orchestrator import run as run_orchestrator  # noqa: E402

app = FastAPI(title="Contoso HR Multi-Agent Service")


class AskBody(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
        "foundry_agent_id": os.environ.get("FOUNDRY_AGENT_ID", ""),
    }


@app.post("/ask")
async def ask(body: AskBody) -> dict:
    t0 = time.perf_counter()
    answer = await run_orchestrator(body.question)
    return {
        "answer": answer,
        "elapsed_sec": round(time.perf_counter() - t0, 2),
    }
