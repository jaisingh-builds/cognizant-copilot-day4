"""Day 5 · Lab 5 · Part 2a — FoundryDelegateePlugin.

Wraps the Day 4 Foundry Agent Service agent as a single SK
kernel-function. The Analyst can call it for questions that need
multi-step reasoning beyond what the base gpt-4o call gives.

Fallback path: if FOUNDRY_AGENT_ID=fallback, the plugin uses a
direct Azure OpenAI call with a reasoning system prompt. Lets the
capstone run even if Day 4 wasn't completed.
"""
import os
import time
from typing import Annotated

from semantic_kernel.functions import kernel_function


class FoundryDelegateePlugin:
    @kernel_function(
        description=(
            "Delegate a multi-step reasoning question to the Contoso "
            "Foundry reasoning agent. Use ONLY for complex questions "
            "that require comparing multiple facts, interpreting "
            "policy edge-cases, or reasoning about counter-factuals. "
            "Do NOT use for straight lookups (use HRLookup instead). "
            "Returns the Foundry agent's analysis."
        ),
        name="ask_foundry",
    )
    def ask_foundry(
        self,
        question: Annotated[
            str,
            "The reasoning question. Include all relevant facts; the "
            "Foundry agent does not have access to your SK context.",
        ],
    ) -> str:
        agent_id = os.environ.get("FOUNDRY_AGENT_ID", "fallback")
        if agent_id == "fallback":
            return self._fallback_call(question)
        return self._foundry_call(agent_id, question)

    # ------------------------------------------------------------
    def _foundry_call(self, agent_id: str, question: str) -> str:
        from azure.ai.agents import AgentsClient
        from azure.identity import DefaultAzureCredential

        endpoint = os.environ.get(
            "FOUNDRY_PROJECT_ENDPOINT",
            os.environ.get("PROJECT_CONNECTION_STRING", ""),
        )
        if not endpoint:
            return "[foundry delegatee] FOUNDRY_PROJECT_ENDPOINT not set"

        client = AgentsClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )

        thread = client.threads.create()
        client.messages.create(
            thread_id=thread.id, role="user", content=question
        )
        run = client.runs.create_and_process(
            thread_id=thread.id, agent_id=agent_id
        )

        if str(run.status).lower() not in ("runstatus.completed", "completed"):
            return f"[foundry delegatee] run status: {run.status}"

        msgs = list(client.messages.list(thread_id=thread.id, order="desc"))
        for m in msgs:
            if m.role == "assistant" and m.content:
                first = m.content[0]
                if hasattr(first, "text"):
                    return first.text.value
        return "[foundry delegatee] no assistant message found"

    # ------------------------------------------------------------
    def _fallback_call(self, question: str) -> str:
        """No Foundry agent? Direct Azure OpenAI call with reasoning prompt."""
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2024-08-01-preview"
            ),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        )
        resp = client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the Contoso reasoning specialist. "
                        "Break the question into sub-questions, "
                        "address each, then synthesize. Be concrete. "
                        "Max 150 words."
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""
