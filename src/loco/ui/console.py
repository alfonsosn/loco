"""Console wrapper for Rich-based terminal UI."""

import sys
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console as RichConsole
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape as escape_markup
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from loco.config import get_config_dir


class Console:
    """Wrapper around Rich console with loco-specific functionality."""

    def __init__(self) -> None:
        self.console = RichConsole()
        self._setup_prompt_session()

    def _setup_prompt_session(self) -> None:
        """Set up the prompt toolkit session with history."""
        history_dir = get_config_dir() / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "prompt_history"

        # Claude Code-style prompt: bold > with subtle styling
        self.prompt_style = Style.from_dict({
            "prompt": "bold ansibrightcyan",
            "prompt-suffix": "",
        })

        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_file)),
            style=self.prompt_style,
            multiline=False,
        )

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to console."""
        self.console.print(*args, **kwargs)

    def print_markdown(self, text: str) -> None:
        """Render and print markdown text."""
        md = Markdown(text)
        self.console.print(md)

    def print_code(self, code: str, language: str = "python") -> None:
        """Print syntax-highlighted code."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def print_error(self, message: str) -> None:
        """Print an error message (escapes Rich markup in message)."""
        self.console.print(f"[bold red]Error:[/bold red] {escape_markup(str(message))}")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.console.print(f"[yellow]Warning:[/yellow] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[green]{message}[/green]")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[dim]{message}[/dim]")

    def print_model_info(self, model: str) -> None:
        """Print current model information."""
        self.console.print(f"[dim]Model: {model}[/dim]")

    def print_welcome(self, model: str, cwd: str) -> None:
        """Print welcome message - minimal Claude Code style."""
        self.console.print()
        self.console.print("[bold]loco[/bold] [dim]v0.1.0[/dim]")
        self.console.print(f"[dim]cwd:[/dim] {cwd}")
        self.console.print(f"[dim]model:[/dim] {model}")
        self.console.print()
        self.console.print("[dim]/help for commands · ctrl+c to exit[/dim]")
        self.console.print()

    def get_input(self, prompt: str = "> ") -> str | None:
        """Get user input with prompt toolkit."""
        try:
            # Use formatted prompt with style
            return self.prompt_session.prompt(
                [("class:prompt", prompt), ("", " ")],
            )
        except (EOFError, KeyboardInterrupt):
            return None

    def get_multiline_input(self, prompt: str = "> ") -> str | None:
        """Get multiline user input (Ctrl+D to submit)."""
        try:
            return self.prompt_session.prompt(
                [("class:prompt", prompt)],
                multiline=True,
            )
        except (EOFError, KeyboardInterrupt):
            return None

    def create_live(self) -> Live:
        """Create a Live context for streaming output."""
        return Live(
            "",
            console=self.console,
            refresh_per_second=10,
            transient=True,
        )

    def clear(self) -> None:
        """Clear the console."""
        self.console.clear()

    @property
    def width(self) -> int:
        """Get console width."""
        return self.console.width


# Global console instance
_console: Console | None = None


def get_console() -> Console:
    """Get the global console instance."""
    global _console
    if _console is None:
        _console = Console()
    return _console
