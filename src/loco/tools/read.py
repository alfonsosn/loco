"""Read file tool for loco."""

import os
from pathlib import Path
from typing import Any

from loco.tools.base import Tool, tool_registry
from loco.telemetry import get_tracker


class ReadTool(Tool):
    """Tool for reading file contents."""

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file. Returns the file contents with line numbers. "
            "Use this to examine existing files before modifying them."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute or relative path to the file to read.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed). Optional.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Optional, defaults to 2000.",
                },
            },
            "required": ["file_path"],
        }

    def execute(
        self,
        file_path: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Read file contents with optional offset and limit."""
        # Resolve path
        path = Path(file_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            return f"Error: File not found: {path}"

        if not path.is_file():
            return f"Error: Not a file: {path}"

        # Set defaults
        start_line = (offset or 1) - 1  # Convert to 0-indexed
        max_lines = limit or 2000

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading file: {e}"

        # Apply offset and limit
        total_lines = len(lines)
        start_line = max(0, min(start_line, total_lines))
        end_line = min(start_line + max_lines, total_lines)
        selected_lines = lines[start_line:end_line]

        # Track file read for duplicate detection
        get_tracker().track_file_read(str(path))

        # Format with line numbers
        result_lines = []
        for i, line in enumerate(selected_lines, start=start_line + 1):
            # Truncate very long lines
            if len(line) > 2000:
                line = line[:2000] + "...[truncated]\n"
            result_lines.append(f"{i:6}\t{line.rstrip()}")

        result = "\n".join(result_lines)

        # Add metadata
        if start_line > 0 or end_line < total_lines:
            result = f"[Showing lines {start_line + 1}-{end_line} of {total_lines}]\n\n{result}"

        return result


# Register the tool
tool_registry.register(ReadTool())
