"""Base tool class and registry for loco."""

from abc import ABC, abstractmethod
from typing import Any

from loco.telemetry import track_tool, get_tracker


class Tool(ABC):
    """Base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the tool does."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters."""
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool with the given arguments.

        Returns:
            A string result to be passed back to the LLM.
        """
        ...

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI tool format for LiteLLM."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Get all tools in OpenAI format."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with the given arguments."""
        tool = self.get(name)
        if tool is None:
            return f"Error: Unknown tool '{name}'"

        try:
            with track_tool(name):
                return tool.execute(**arguments)
        except Exception as e:
            return f"Error executing {name}: {e}"


# Global registry instance
tool_registry = ToolRegistry()
