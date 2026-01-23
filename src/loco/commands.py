"""Commands system for loco - reusable prompts that teach the LLM specific tasks."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from loco.config import get_config_dir


@dataclass
class Command:
    """A command definition loaded from a COMMAND.md file."""

    name: str
    description: str
    content: str  # Full markdown content (instructions)
    allowed_tools: list[str] | None = None
    model: str | None = None
    user_invocable: bool = True
    path: Path | None = None

    def get_system_prompt_addition(self) -> str:
        """Get the content to add to system prompt when command is active."""
        return f"""
--- COMMAND: {self.name} ---
{self.content}
--- END COMMAND ---
"""


@dataclass
class CommandRegistry:
    """Registry for discovering and managing commands."""

    commands: dict[str, Command] = field(default_factory=dict)
    _discovered: bool = False

    def discover(self, project_dir: Path | None = None) -> None:
        """Discover commands from all locations.

        Locations (in precedence order, later overrides earlier):
        1. User commands: ~/.config/loco/commands/
        2. Claude Desktop commands: .claude/commands/ (for compatibility)
        3. Project commands: .loco/commands/ (highest priority)

        Note: .claude/ support enables seamless integration with Claude Desktop
        configurations. Both .claude/ and .loco/ can coexist in the same project.
        """
        self.commands.clear()

        # User commands (lowest precedence)
        user_commands_dir = get_config_dir() / "commands"
        self._load_commands_from_dir(user_commands_dir)

        # Project directory to search
        search_dir = project_dir if project_dir else Path.cwd()

        # Claude Desktop commands (middle precedence)
        claude_commands_dir = search_dir / ".claude" / "commands"
        self._load_commands_from_dir(claude_commands_dir)

        # Loco project commands (highest precedence)
        loco_commands_dir = search_dir / ".loco" / "commands"
        self._load_commands_from_dir(loco_commands_dir)

        self._discovered = True

    def _load_commands_from_dir(self, commands_dir: Path) -> None:
        """Load all commands from a directory."""
        if not commands_dir.exists():
            return

        # Commands are in subdirectories: commands/command-name/COMMAND.md
        for command_dir in commands_dir.iterdir():
            if not command_dir.is_dir():
                continue

            command_file = command_dir / "COMMAND.md"
            if not command_file.exists():
                continue

            try:
                command = self._parse_command_file(command_file)
                if command:
                    self.commands[command.name] = command
            except Exception as e:
                # Log but don't fail on individual command errors
                print(f"Warning: Failed to load command from {command_file}: {e}")

    def _parse_command_file(self, path: Path) -> Command | None:
        """Parse a COMMAND.md file into a Command object."""
        content = path.read_text()

        # Parse YAML frontmatter
        frontmatter: dict[str, Any] = {}
        body = content

        if content.startswith("---"):
            # Find the closing ---
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if match:
                try:
                    frontmatter = yaml.safe_load(match.group(1)) or {}
                except yaml.YAMLError:
                    frontmatter = {}
                body = match.group(2)

        # Extract required fields
        name = frontmatter.get("name", path.parent.name)
        description = frontmatter.get("description", "")

        if not description:
            # Try to extract from first paragraph
            lines = body.strip().split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break

        # Parse allowed-tools
        allowed_tools = frontmatter.get("allowed-tools")
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",")]

        return Command(
            name=name,
            description=description,
            content=body.strip(),
            allowed_tools=allowed_tools,
            model=frontmatter.get("model"),
            user_invocable=frontmatter.get("user-invocable", True),
            path=path,
        )

    def get(self, name: str) -> Command | None:
        """Get a command by name."""
        if not self._discovered:
            self.discover()
        return self.commands.get(name)

    def get_all(self) -> list[Command]:
        """Get all discovered commands."""
        if not self._discovered:
            self.discover()
        return list(self.commands.values())

    def get_user_invocable(self) -> list[Command]:
        """Get all commands that can be manually invoked."""
        return [c for c in self.get_all() if c.user_invocable]

    def get_command_descriptions(self) -> str:
        """Get a formatted string of all command descriptions for the LLM."""
        commands = self.get_all()
        if not commands:
            return ""

        lines = ["Available commands (use when relevant):"]
        for command in commands:
            lines.append(f"- {command.name}: {command.description}")

        return "\n".join(lines)

    def match_commands(self, user_input: str, limit: int = 3) -> list[Command]:
        """Find commands that might be relevant to the user's request.

        This is a simple keyword-based matching. For better results,
        you could use embeddings or LLM-based matching.
        """
        if not self._discovered:
            self.discover()

        user_lower = user_input.lower()
        scored_commands: list[tuple[int, Command]] = []

        for command in self.commands.values():
            score = 0
            desc_lower = command.description.lower()
            name_lower = command.name.lower()

            # Check if command name is mentioned
            if name_lower in user_lower:
                score += 10

            # Check keyword overlap
            desc_words = set(desc_lower.split())
            user_words = set(user_lower.split())
            overlap = desc_words & user_words
            score += len(overlap)

            # Check for common task keywords
            task_keywords = {
                "review": ["review", "check", "analyze", "audit"],
                "test": ["test", "testing", "spec", "unit"],
                "debug": ["debug", "fix", "error", "bug", "issue"],
                "refactor": ["refactor", "clean", "improve", "optimize"],
                "document": ["document", "docs", "readme", "comment"],
            }

            for category, keywords in task_keywords.items():
                if any(kw in user_lower for kw in keywords):
                    if any(kw in desc_lower for kw in keywords):
                        score += 5

            if score > 0:
                scored_commands.append((score, command))

        # Sort by score descending and return top matches
        scored_commands.sort(key=lambda x: x[0], reverse=True)
        return [command for _, command in scored_commands[:limit]]


# Global registry instance
command_registry = CommandRegistry()


def get_commands_system_prompt_section() -> str:
    """Get the commands section to add to the system prompt."""
    descriptions = command_registry.get_command_descriptions()
    if not descriptions:
        return ""

    return f"""

{descriptions}

When a command matches the user's request, you should follow its instructions.
"""
