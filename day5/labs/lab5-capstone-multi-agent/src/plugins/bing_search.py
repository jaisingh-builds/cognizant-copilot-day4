"""Day 5 · Lab 5 · Part 1b — BingSearchPlugin.

Real-web search via Bing v7 API, with a local mock fallback for
environments where Bing isn't available. Controlled by USE_BING_MOCK.
"""
import os
from typing import Annotated

import requests
from semantic_kernel.functions import kernel_function

from .bing_mock import mock_search  # noqa: E402


class BingSearchPlugin:
    @kernel_function(
        description=(
            "Search the public web for external/industry information "
            "on a topic. Use ONLY when the question needs context "
            "from outside Contoso — industry benchmarks, market "
            "data, comparative studies. Do NOT use for internal "
            "Contoso policies or employee data (use HRLookup "
            "instead). Returns the top 3 result snippets."
        ),
        name="search",
    )
    def search(
        self,
        query: Annotated[str, "The search query. Be specific."],
    ) -> str:
        if os.environ.get("USE_BING_MOCK", "").lower() == "true":
            return mock_search(query)

        key = os.environ.get("BING_SEARCH_API_KEY")
        endpoint = os.environ.get(
            "BING_SEARCH_ENDPOINT",
            "https://api.bing.microsoft.com/v7.0/search",
        )
        if not key:
            # No Bing key, no mock — fail loudly so the Researcher knows.
            return (
                "BING_SEARCH_API_KEY not set and USE_BING_MOCK is not "
                "'true'. Cannot perform external search."
            )

        try:
            resp = requests.get(
                endpoint,
                headers={"Ocp-Apim-Subscription-Key": key},
                params={"q": query, "count": 3, "textDecorations": False},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            return f"Bing search failed: {exc}. Consider USE_BING_MOCK=true."

        pages = data.get("webPages", {}).get("value", [])[:3]
        if not pages:
            return "No results."
        return "\n\n".join(
            f"[{i+1}] {p.get('name', '').strip()}\n"
            f"    {p.get('url', '')}\n"
            f"    {p.get('snippet', '').strip()}"
            for i, p in enumerate(pages)
        )
