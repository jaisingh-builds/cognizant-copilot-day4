"""
Day 4 — Lab 2 — Foundry Agent Service demo.

Creates a Contoso HR agent with two function tools, drives a
multi-turn thread, and prints both tool calls and final messages.

Requires:
    pip install azure-ai-projects azure-ai-agents azure-identity python-dotenv

Env (.env in this folder):
    PROJECT_ENDPOINT           Foundry project endpoint (Overview → Project details
                               → "Azure AI Foundry project endpoint"). Shape:
                               https://<account>.services.ai.azure.com/api/projects/<project>
    MODEL_DEPLOYMENT_NAME      e.g. gpt-4o-training
"""

import json
import os
import sys
from typing import Any

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FunctionTool, ListSortOrder, ToolSet
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
MODEL_NAME       = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-training")

# --- Mock HR backend ------------------------------------------------------
# Seeded from Day 1 Dataverse. Replace with a real API call in production.

EMPLOYEES = {
    "E-1042": {"name": "Priya Raman",  "vacation_days": 12},
    "E-1357": {"name": "Aisha Patel",  "vacation_days": 8},
    "E-1199": {"name": "Daniel Okafor", "vacation_days": 15},
}

POLICIES = {
    "vacation": (
        "Contoso full-time employees accrue vacation at 12–20 days/year "
        "based on region. Engineers in India: 12 days/year. Managers "
        "must approve any request > 5 consecutive days."
    ),
    "sick": (
        "Unlimited sick leave with manager notification. More than 3 "
        "consecutive days requires a medical certificate."
    ),
    "parental": (
        "16 weeks paid for primary caregivers, 4 weeks for secondary. "
        "Must be taken within the first 12 months of the child's birth or "
        "adoption."
    ),
}

# --- Tool implementations -------------------------------------------------

def get_vacation_balance(employee_id: str) -> str:
    """Return the current vacation balance for an employee."""
    emp = EMPLOYEES.get(employee_id)
    if not emp:
        return json.dumps({"error": f"Unknown employee {employee_id}"})
    return json.dumps({
        "employee_id":   employee_id,
        "name":          emp["name"],
        "vacation_days": emp["vacation_days"],
    })


def get_hr_policy(topic: str) -> str:
    """Return the Contoso policy on a given HR topic.

    `topic` must be one of: vacation, sick, parental.
    """
    policy = POLICIES.get(topic.lower())
    if not policy:
        return json.dumps({"error": f"No policy for topic '{topic}'"})
    return json.dumps({"topic": topic, "policy": policy})


FUNCTIONS = {get_vacation_balance, get_hr_policy}

AGENT_NAME = "contoso-hr-foundry-agent"
AGENT_INSTRUCTIONS = (
    "You are the Contoso HR helper. Use get_vacation_balance for balance "
    "questions and get_hr_policy for policy questions (topic must be one "
    "of: vacation, sick, parental). Be concise. If the user hasn't given "
    "you an employee ID when you need one, ask."
)


def build_client_and_toolset() -> tuple[AgentsClient, ToolSet]:
    """Construct an AgentsClient with auto-function-calls enabled on our tools."""
    client = AgentsClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    toolset = ToolSet()
    toolset.add(FunctionTool(functions=FUNCTIONS))
    client.enable_auto_function_calls(toolset)
    return client, toolset


def get_or_create_agent(client: AgentsClient, toolset: ToolSet):
    """Reuse a previously-created agent by name if it exists, else create."""
    for a in client.list_agents():
        if a.name == AGENT_NAME:
            print(f"Reusing agent: {a.id}")
            return a
    agent = client.create_agent(
        model=MODEL_NAME,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        toolset=toolset,
    )
    print(f"Created agent: {agent.id}")
    return agent


def main() -> None:
    client, toolset = build_client_and_toolset()
    agent = get_or_create_agent(client, toolset)

    thread = client.threads.create()
    print(f"Thread: {thread.id}")

    def send(user_message: str) -> None:
        """Send one user turn, let the SDK auto-run tools, print the reply."""
        print(f"\n> {user_message}")
        client.messages.create(thread_id=thread.id, role="user", content=user_message)
        run = client.runs.create_and_process(
            thread_id=thread.id, agent_id=agent.id, toolset=toolset
        )
        if run.status != "completed":
            last_error = getattr(run, "last_error", None)
            print(f"[run failed — status={run.status} error={last_error}]")
            return
        reply = client.messages.get_last_message_text_by_role(
            thread_id=thread.id, role="assistant"
        )
        if reply is not None:
            print(reply.text.value)

    # Part 2 — first tool call
    send("What's my vacation balance? I'm employee E-1042.")

    # Part 4 — multi-turn with state + second tool
    send("What's our parental leave policy?")
    send("And for sick leave?")
    send("Now — I'm actually E-1357. What's MY vacation balance?")

    # Cleanup is optional. Leaving the agent for Lab 3 reuse.
    print(f"\nAgent ID (save for Lab 3): {agent.id}")


if __name__ == "__main__":
    main()
