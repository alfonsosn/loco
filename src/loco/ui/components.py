"""UI components for loco - minimal Claude Code-inspired output."""

from contextlib import contextmanager
from typing import Any, Generator

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner as RichSpinner
from rich.syntax import Syntax
from rich.text import Text


class Spinner:
    """A spinner for showing activity."""

    def __init__(self, console: Console, message: str = "Thinking...") -> None:
        self.console = console
        self.message = message
        self._live: Live | None = None

    def __enter__(self) -> "Spinner":
        spinner = RichSpinner("dots", text=Text(self.message, style="dim"))
        self._live = Live(spinner, console=self.console, transient=True)
        self._live.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._live:
            self._live.__exit__(*args)
            self._live = None

    def update(self, message: str) -> None:
        """Update the spinner message."""
        if self._live:
            spinner = RichSpinner("dots", text=Text(message, style="dim"))
            self._live.update(spinner)


class ToolDisplay:
    """Minimal tool call/result display - Claude Code style."""

    @staticmethod
    def _format_primary_arg(name: str, arguments: dict[str, Any]) -> str:
        """Get the most relevant argument to display inline."""
        # Priority order for common tools
        priority_keys = ["file_path", "path", "command", "pattern", "query"]
        for key in priority_keys:
            if key in arguments:
                val = arguments[key]
                if isinstance(val, str):
                    # Truncate long values
                    return val[:60] + "..." if len(val) > 60 else val
        # Fall back to first string argument
        for val in arguments.values():
            if isinstance(val, str):
                return val[:60] + "..." if len(val) > 60 else val
        return ""

    @staticmethod
    def tool_call(name: str, arguments: dict[str, Any], console: Console) -> None:
        """Display a minimal tool call line."""
        primary = ToolDisplay._format_primary_arg(name, arguments)
        if primary:
            console.print(f"[dim]●[/dim] [cyan]{name}[/cyan] [dim]{primary}[/dim]")
        else:
            console.print(f"[dim]●[/dim] [cyan]{name}[/cyan]")

    @staticmethod
    def tool_result(name: str, result: str, success: bool, console: Console) -> None:
        """Display tool result - minimal for success, visible for errors."""
        if not success:
            # Show errors prominently
            console.print(f"  [red]✗[/red] [dim]{result[:200]}[/dim]")
        elif result and len(result.strip()) > 0:
            # For successful results, show a brief summary
            lines = result.strip().split("\n")
            if len(lines) == 1 and len(lines[0]) < 80:
                # Short single-line result - show it
                console.print(f"  [dim]→ {lines[0]}[/dim]")
            elif len(lines) <= 5:
                # Few lines - show them indented
                for line in lines[:5]:
                    truncated = line[:100] + "..." if len(line) > 100 else line
                    console.print(f"  [dim]{truncated}[/dim]")
            else:
                # Many lines - just show count
                console.print(f"  [dim]→ {len(lines)} lines[/dim]")

    @staticmethod
    def tool_result_expanded(name: str, result: str, success: bool, console: Console) -> None:
        """Display full tool result (for explicit show)."""
        max_lines = 30
        lines = result.split("\n")

        if len(lines) > max_lines:
            for line in lines[:max_lines]:
                console.print(f"  [dim]{line}[/dim]")
            console.print(f"  [dim]... ({len(lines) - max_lines} more lines)[/dim]")
        else:
            for line in lines:
                console.print(f"  [dim]{line}[/dim]")

    @staticmethod
    def error(message: str, console: Console) -> None:
        """Display an error message."""
        console.print(f"[red]✗ Error:[/red] {message}")


# Backwards compatibility alias
class ToolPanel:
    """Deprecated - use ToolDisplay instead."""
    tool_call = ToolDisplay.tool_call
    tool_result = ToolDisplay.tool_result
    error = ToolDisplay.error


class StreamingMarkdown:
    """Helper for streaming markdown content."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.content = ""
        self._live: Live | None = None

    def __enter__(self) -> "StreamingMarkdown":
        self._live = Live(
            "",
            console=self.console,
            refresh_per_second=10,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._live:
            # Final render
            if self.content:
                self._live.update(Markdown(self.content))
            self._live.__exit__(*args)
            self._live = None

    def update(self, content: str) -> None:
        """Update the streaming content."""
        self.content = content
        if self._live and content:
            self._live.update(Markdown(content))

    def append(self, chunk: str) -> None:
        """Append a chunk to the content."""
        self.content += chunk
        if self._live and self.content:
            self._live.update(Markdown(self.content))


@contextmanager
def thinking_spinner(console: Console) -> Generator[Spinner, None, None]:
    """Context manager for a thinking spinner."""
    with Spinner(console, "Thinking...") as spinner:
        yield spinner
