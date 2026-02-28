"""Tool registry for Synapse Agent.

Tools are the actions the agent can take to interact with the world.
Each tool implements the BaseTool interface.
"""

from .base import BaseTool, ToolResult
from .web_search import WebSearchTool
from .calculator import CalculatorTool
from .calendar_tool import CalendarTool
from .knowledge_base import KnowledgeBaseTool

# Tool registry — maps tool names to their classes
TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    "web_search": WebSearchTool,
    "calculator": CalculatorTool,
    "calendar": CalendarTool,
    "knowledge_base": KnowledgeBaseTool,
    "llm_reasoning": None,  # Handled directly by executor
}


def get_tool(name: str) -> BaseTool | None:
    """Get a tool instance by name."""
    tool_class = TOOL_REGISTRY.get(name)
    if tool_class is None:
        return None
    return tool_class()


def get_available_tools() -> list[str]:
    """Get list of all available tool names."""
    return list(TOOL_REGISTRY.keys())
