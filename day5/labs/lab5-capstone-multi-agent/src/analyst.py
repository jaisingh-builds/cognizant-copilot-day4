"""Day 5 · Lab 5 · Part 2b — Analyst with Foundry delegation."""
import os
import sys

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import KernelArguments

# Lab 2's PolicyComparePlugin
_LAB2 = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "lab2-orchestration-patterns",
        "src",
    )
)
sys.path.insert(0, _LAB2)
from shared.analyst_tools import PolicyComparePlugin  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plugins.foundry_delegatee import FoundryDelegateePlugin  # noqa: E402


def build_analyst_kernel() -> Kernel:
    kernel = Kernel()
    kernel.add_service(
        AzureChatCompletion(
            service_id="default",
            deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    )
    kernel.add_plugin(PolicyComparePlugin(), plugin_name="PolicyCompare")
    kernel.add_plugin(
        FoundryDelegateePlugin(), plugin_name="FoundryDelegatee"
    )
    return kernel


def build_analyst(kernel: Kernel) -> ChatCompletionAgent:
    settings = OpenAIChatPromptExecutionSettings(
        service_id="default",
        function_choice_behavior=FunctionChoiceBehavior.Auto(),
    )
    return ChatCompletionAgent(
        kernel=kernel,
        name="Analyst",
        instructions=(
            "You are the Analyst. You receive FACTS from the "
            "Researcher. Produce ANALYSIS — comparisons, percentages, "
            "implications. Tool routing:\n"
            "  - Straight numerical comparison against Contoso policy\n"
            "      → PolicyCompare.compare_vacation_usage\n"
            "  - Multi-step reasoning, policy interpretation,\n"
            "    counter-factual analysis\n"
            "      → FoundryDelegatee.ask_foundry (pass ALL relevant\n"
            "         facts in the question — Foundry doesn't see "
            "         your context)\n\n"
            "Output a labelled ANALYSIS section. Do NOT write the "
            "final user-facing answer — the Writer does."
        ),
        arguments=KernelArguments(settings=settings),
    )


async def ask_analyst(question: str, facts: str) -> str:
    kernel = build_analyst_kernel()
    agent = build_analyst(kernel)
    history = ChatHistory()
    history.add_user_message(
        f"Original question:\n{question}\n\nResearcher FACTS:\n{facts}"
    )
    reply = ""
    async for item in agent.invoke(messages=history):
        msg = item.message
        if msg.role.value == "assistant" and msg.content:
            reply = str(msg.content)
    return reply
