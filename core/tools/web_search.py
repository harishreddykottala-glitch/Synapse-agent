"""Web search tool for Synapse Agent."""

import os
import aiohttp
from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """Search the web using Tavily API or fallback to a simple search."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for information on a topic."

    async def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, output="", error="No query provided")

        api_key = os.getenv("TAVILY_API_KEY", "")
        if api_key:
            return await self._tavily_search(query, api_key)
        return await self._fallback_search(query)

    async def _tavily_search(self, query: str, api_key: str) -> ToolResult:
        """Search using Tavily API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/search",
                    json={"query": query, "api_key": api_key, "max_results": 5},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        output = "\n\n".join(
                            f"**{r.get('title', 'Untitled')}**\n{r.get('content', '')}\nSource: {r.get('url', '')}"
                            for r in results
                        )
                        return ToolResult(
                            success=True,
                            output=output or "No results found.",
                            data={"results": results},
                        )
                    return ToolResult(success=False, output="", error=f"Tavily API error: {resp.status}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Search error: {str(e)}")

    async def _fallback_search(self, query: str) -> ToolResult:
        """Fallback: return a message that no search API is configured."""
        return ToolResult(
            success=True,
            output=f"[No search API configured] The agent would search for: '{query}'. "
                   "Configure TAVILY_API_KEY in .env for live web search.",
            data={"query": query, "fallback": True},
        )
