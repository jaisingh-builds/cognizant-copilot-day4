"""Day 5 · Lab 5 · Part 1c — Researcher with HR + Bing."""
import asyncio
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

# Reach into Lab 1 for HRLookupPlugin.
_LAB1 = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "lab1-semantic-kernel-setup",
        "src",
    )
)
import importlib.util as _ilu


def _load_file_module(name: str, path: str):
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HRLookupPlugin = _load_file_module(
    "_lab1_hr_lookup", os.path.join(_LAB1, "plugins", "hr_lookup.py")
).HRLookupPlugin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plugins.bing_search import BingSearchPlugin  # noqa: E402


def build_researcher_kernel() -> Kernel:
    kernel = Kernel()
    kernel.add_service(
        AzureChatCompletion(
            service_id="default",
            deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    )
    kernel.add_plugin(HRLookupPlugin(), plugin_name="HRLookup")
    kernel.add_plugin(BingSearchPlugin(), plugin_name="BingSearch")
    return kernel


def build_researcher(kernel: Kernel) -> ChatCompletionAgent:
    settings = OpenAIChatPromptExecutionSettings(
        service_id="default",
        function_choice_behavior=FunctionChoiceBehavior.Auto(),
    )
    return ChatCompletionAgent(
        kernel=kernel,
        name="Researcher",
        instructions=(
            "You are the Researcher. Gather raw facts only. Use the "
            "right tool for each sub-question:\n"
            "  - Specific Contoso employee data → HRLookup.get_vacation_balance\n"
            "  - Internal Contoso policy text → HRLookup.get_hr_policy\n"
            "  - External / industry context → BingSearch.search\n\n"
            "If a question has both internal and external aspects, "
            "call BOTH tools. Never paraphrase or analyse. Return "
            "raw results as labelled FACTS in the format:\n"
            "FACTS:\n"
            "- <tool_name>(<args>): <raw result>\n"
        ),
        arguments=KernelArguments(settings=settings),
    )


async def ask_researcher(question: str) -> str:
    kernel = build_researcher_kernel()
    agent = build_researcher(kernel)
    history = ChatHistory()
    history.add_user_message(question)
    reply = ""
    async for item in agent.invoke(messages=history):
        msg = item.message
        if msg.role.value == "assistant" and msg.content:
            reply = str(msg.content)
    return reply


async def _main() -> None:
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else (
            "How does Contoso's parental leave policy compare to the "
            "industry average in Europe?"
        )
    )
    print(f"QUESTION: {question}\n")
    print(await ask_researcher(question))


if __name__ == "__main__":
    asyncio.run(_main())
