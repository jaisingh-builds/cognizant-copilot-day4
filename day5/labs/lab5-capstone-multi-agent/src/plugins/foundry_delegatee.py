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
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        conn_str = os.environ["PROJECT_CONNECTION_STRING"]
        client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=conn_str,
        )

        thread = client.agents.create_thread()
        client.agents.create_message(
            thread_id=thread.id, role="user", content=question
        )
        run = client.agents.create_run(
            thread_id=thread.id, agent_id=agent_id
        )

        # Same poll loop as Day 4 Lab 2.
        deadline = time.time() + 60
        while time.time() < deadline:
            run = client.agents.get_run(
                thread_id=thread.id, run_id=run.id
            )
            if run.status in ("completed", "failed", "cancelled"):
                break
            if run.status == "requires_action":
                # This capstone's Foundry agent doesn't have tools
                # we need to satisfy here — if it does in your real
                # deployment, handle tool_outputs like Day 4 Lab 2.
                return (
                    "[foundry delegatee] agent asked for tool output; "
                    "not wired in this lab. Returning abstain."
                )
            time.sleep(1)

        if run.status != "completed":
            return f"[foundry delegatee] run ended in status: {run.status}"

        msgs = client.agents.list_messages(thread_id=thread.id)
        for m in msgs.data:
            if m.role == "assistant":
                # list_messages returns newest first in the Day 4 SDK.
                if m.content and m.content[0].type == "text":
                    return m.content[0].text.value
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
