"""Edit file tool for loco."""

import difflib
from pathlib import Path
from typing import Any

from loco.tools.base import Tool, tool_registry
from loco.rewind import get_rewind_manager, ChangeType


def generate_diff(old_string: str, new_string: str, context_lines: int = 3) -> str:
    """Generate a unified diff between old and new strings."""
    old_lines = old_string.splitlines(keepends=True)
    new_lines = new_string.splitlines(keepends=True)

    # Ensure both end with newlines for clean diff
    if old_lines and not old_lines[-1].endswith('\n'):
        old_lines[-1] += '\n'
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines[-1] += '\n'

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        lineterm='',
        n=context_lines,
    )

    return ''.join(diff)


class EditTool(Tool):
    """Tool for editing files via string replacement."""

    @property
    def name(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing a specific string with a new string. "
            "The old_string must match exactly (including whitespace and indentation). "
            "Use the read tool first to see the exact content to replace."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute or relative path to the file to edit.",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace. Must match exactly.",
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace old_string with.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "If true, replace all occurrences. Default is false (replace first only).",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """Edit a file by string replacement."""
        # Resolve path
        path = Path(file_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            return f"Error: File not found: {path}"

        if not path.is_file():
            return f"Error: Not a file: {path}"

        # Capture state before edit for REWIND
        rewind_manager = get_rewind_manager()
        if rewind_manager:
            rewind_manager.capture_before(str(path))

        # Read current content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

        # Check if old_string exists
        if old_string not in content:
            # Try to provide helpful feedback
            lines_with_partial = []
            for i, line in enumerate(content.split("\n"), 1):
                if old_string.split("\n")[0].strip() in line:
                    lines_with_partial.append(i)

            hint = ""
            if lines_with_partial:
                hint = f" Partial matches found on lines: {lines_with_partial[:5]}"

            return f"Error: old_string not found in file.{hint}"

        # Count occurrences
        count = content.count(old_string)

        if count > 1 and not replace_all:
            return (
                f"Error: Found {count} occurrences of old_string. "
                "Either make old_string more specific, or set replace_all=true."
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced_count = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replaced_count = 1

        # Generate diff for display
        diff = generate_diff(old_string, new_string)

        # Write back
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return f"Error writing file: {e}"

        # Capture state after edit for REWIND
        if rewind_manager:
            rewind_manager.capture_after(str(path), new_content, ChangeType.MODIFIED)

        # Return with diff
        return f"✓ {path}\n{diff}"


# Register the tool
tool_registry.register(EditTool())
