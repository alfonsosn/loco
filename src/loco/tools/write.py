"""Write file tool for loco."""

import os
from pathlib import Path
from typing import Any

from loco.tools.base import Tool, tool_registry
from loco.rewind import get_rewind_manager, ChangeType


class WriteTool(Tool):
    """Tool for writing/creating files."""

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. Creates the file if it doesn't exist, "
            "or overwrites if it does. Creates parent directories as needed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute or relative path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["file_path", "content"],
        }

    def execute(self, file_path: str, content: str) -> str:
        """Write content to a file."""
        # Resolve path
        path = Path(file_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path

        # Capture state before write for REWIND
        rewind_manager = get_rewind_manager()
        if rewind_manager:
            rewind_manager.capture_before(str(path))

        # Create parent directories if needed
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"Error creating directory: {e}"

        # Check if file exists (for messaging)
        existed = path.exists()

        # Write the file
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return f"Error writing file: {e}"

        # Capture state after write for REWIND
        if rewind_manager:
            change_type = ChangeType.MODIFIED if existed else ChangeType.CREATED
            rewind_manager.capture_after(str(path), content, change_type)

        # Count lines for feedback
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

        action = "Updated" if existed else "Created"
        return f"{action} {path} ({line_count} lines)"


# Register the tool
tool_registry.register(WriteTool())
