"""Day 5 · Lab 5 · Part 3 — Writer (no tools, prose only)."""
import os

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


def build_writer_kernel() -> Kernel:
    kernel = Kernel()
    kernel.add_service(
        AzureChatCompletion(
            service_id="default",
            deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    )
    return kernel


def build_writer(kernel: Kernel) -> ChatCompletionAgent:
    settings = OpenAIChatPromptExecutionSettings(
        service_id="default",
        function_choice_behavior=FunctionChoiceBehavior.NoneInvoke(),
    )
    return ChatCompletionAgent(
        kernel=kernel,
        name="Writer",
        instructions=(
            "You are the Writer. You receive ANALYSIS from the "
            "Analyst and compose the final user-facing answer in "
            "Contoso house tone: warm, direct, no jargon, no bullet "
            "points unless the user asked. Target 60–80 words. "
            "Cite the one most important number. Do NOT invent data; "
            "only use what the Analyst provided. If the Analyst cited "
            "industry benchmarks, compare Contoso to them in one "
            "clause. End with one forward-looking sentence."
        ),
        arguments=KernelArguments(settings=settings),
    )


async def ask_writer(question: str, analysis: str) -> str:
    kernel = build_writer_kernel()
    agent = build_writer(kernel)
    history = ChatHistory()
    history.add_user_message(
        f"Original question:\n{question}\n\nAnalyst ANALYSIS:\n{analysis}"
    )
    reply = ""
    async for item in agent.invoke(messages=history):
        msg = item.message
        if msg.role.value == "assistant" and msg.content:
            reply = str(msg.content)
    return reply
