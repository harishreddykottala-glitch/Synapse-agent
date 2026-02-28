"""Base tool interface for Synapse Agent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str
    data: dict | None = None
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this tool does."""
        ...

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...
