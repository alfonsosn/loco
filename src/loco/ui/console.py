"""Console wrapper for Rich-based terminal UI."""

import sys
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.application import get_app
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

    # Horizontal padding for the TUI (number of spaces on each side)
    PADDING = 2

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
            "separator": "ansibrightblack",
        })

        # Create key bindings that work like Claude Code
        # - Enter submits (like single-line mode)
        # - Shift+Enter or Alt+Enter adds a newline (for explicit multi-line)
        # - Pasting multiline content works
        kb = KeyBindings()

        @kb.add('enter')
        def _(event):
            """Enter submits the input."""
            event.current_buffer.validate_and_handle()

        @kb.add('c-j')
        def _(event):
            """Ctrl+J inserts a newline for multiline input."""
            event.current_buffer.insert_text('\n')

        @kb.add('escape', 'enter')
        def _(event):
            """Alt+Enter inserts a newline for multiline input."""
            event.current_buffer.insert_text('\n')

        # Continuation prompt aligns with the input after padding + "> "
        continuation = " " * (self.PADDING + 2)
        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_file)),
            style=self.prompt_style,
            multiline=True,  # Allow multiline (for pasting), but Enter submits
            key_bindings=kb,
            prompt_continuation=continuation,
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

    def _pad(self, text: str) -> str:
        """Add horizontal padding to text."""
        padding = " " * self.PADDING
        return f"{padding}{text}"

    def _separator(self) -> str:
        """Create a separator line with padding."""
        padding = " " * self.PADDING
        line_width = max(1, self.console.width - (self.PADDING * 2))
        return f"{padding}[dim]{'─' * line_width}[/dim]"

    def print_welcome(self, model: str, cwd: str) -> None:
        """Print welcome message - minimal Claude Code style."""
        self.console.print()
        self.console.print(self._pad("[bold]loco[/bold] [dim]v0.1.0[/dim]"))
        self.console.print(self._pad(f"[dim]cwd:[/dim] {cwd}"))
        self.console.print(self._pad(f"[dim]model:[/dim] {model}"))
        self.console.print()
        self.console.print(self._pad("[dim]/help for commands · ctrl+j for newline · ctrl+c to exit[/dim]"))
        self.console.print()

    def get_input(self, prompt: str = "> ") -> str | None:
        """Get user input with prompt toolkit."""
        try:
            # Print top separator line (Claude Code style)
            self.console.print()
            self.console.print(self._separator())

            # Use formatted prompt with style and padding
            padding = " " * self.PADDING
            result = self.prompt_session.prompt(
                [("", padding), ("class:prompt", prompt), ("", " ")],
            )

            # Print bottom separator line (only if we got input)
            if result is not None:
                self.console.print(self._separator())

                # Check if pasted content (multiline)
                if '\n' in result:
                    line_count = result.count('\n') + 1
                    self.console.print(self._pad(f"[dim]Pasted {line_count} lines[/dim]"))
                self.console.print()

            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def get_multiline_input(self, prompt: str = "> ") -> str | None:
        """Get multiline user input (Meta+Enter or Esc+Enter to submit)."""
        try:
            # Create temporary key bindings for explicit multiline mode
            kb = KeyBindings()

            @kb.add('enter')
            def _(event):
                """Enter inserts a newline in multiline mode."""
                event.current_buffer.insert_text('\n')

            @kb.add('escape', 'enter')  # Alt/Meta+Enter to submit
            def _(event):
                """Alt+Enter submits."""
                event.current_buffer.validate_and_handle()

            # Print top separator line
            self.console.print(self._separator())
            self.console.print(self._pad("[dim]Alt+Enter to submit, Enter for new line[/dim]"))

            padding = " " * self.PADDING
            result = self.prompt_session.prompt(
                [("", padding), ("class:prompt", prompt)],
                multiline=True,
                key_bindings=kb,
            )

            # Print bottom separator line
            self.console.print(self._separator())

            return result
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
