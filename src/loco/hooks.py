"""Hooks system for loco - shell commands that run at lifecycle events."""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HookEvent(Enum):
    """Lifecycle events where hooks can run."""

    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"


@dataclass
class HookResult:
    """Result from executing a hook."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    # Parsed from JSON stdout on success
    decision: str | None = None  # "allow", "deny", "skip"
    reason: str | None = None
    modified_input: dict[str, Any] | None = None
    additional_context: str | None = None


@dataclass
class Hook:
    """A single hook definition."""

    command: str
    timeout: int = 60  # seconds
    matcher: str | None = None  # Regex pattern to match tool names

    def matches(self, tool_name: str) -> bool:
        """Check if this hook matches the given tool name."""
        if self.matcher is None:
            return True
        try:
            return bool(re.match(self.matcher, tool_name, re.IGNORECASE))
        except re.error:
            return self.matcher.lower() == tool_name.lower()


@dataclass
class HookConfig:
    """Configuration for all hooks."""

    pre_tool_use: list[Hook] = field(default_factory=list)
    post_tool_use: list[Hook] = field(default_factory=list)
    session_start: list[Hook] = field(default_factory=list)
    session_end: list[Hook] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HookConfig":
        """Create HookConfig from a dictionary."""
        config = cls()

        for event_name, hooks_data in data.items():
            hooks = []
            for hook_data in hooks_data:
                if isinstance(hook_data, str):
                    # Simple string command
                    hooks.append(Hook(command=hook_data))
                elif isinstance(hook_data, dict):
                    # Full hook definition
                    matcher = hook_data.get("matcher")
                    hook_list = hook_data.get("hooks", [])
                    for h in hook_list:
                        if isinstance(h, str):
                            hooks.append(Hook(command=h, matcher=matcher))
                        elif isinstance(h, dict) and h.get("type") == "command":
                            hooks.append(Hook(
                                command=h.get("command", ""),
                                timeout=h.get("timeout", 60),
                                matcher=matcher,
                            ))

            # Map event name to attribute
            event_map = {
                "PreToolUse": "pre_tool_use",
                "PostToolUse": "post_tool_use",
                "SessionStart": "session_start",
                "SessionEnd": "session_end",
            }
            attr_name = event_map.get(event_name)
            if attr_name:
                setattr(config, attr_name, hooks)

        return config

    def get_hooks(self, event: HookEvent, tool_name: str | None = None) -> list[Hook]:
        """Get hooks for a specific event, optionally filtered by tool name."""
        hooks_map = {
            HookEvent.PRE_TOOL_USE: self.pre_tool_use,
            HookEvent.POST_TOOL_USE: self.post_tool_use,
            HookEvent.SESSION_START: self.session_start,
            HookEvent.SESSION_END: self.session_end,
        }

        hooks = hooks_map.get(event, [])

        if tool_name is not None:
            hooks = [h for h in hooks if h.matches(tool_name)]

        return hooks


def execute_hook(
    hook: Hook,
    event: HookEvent,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_output: str | None = None,
    cwd: str | None = None,
) -> HookResult:
    """Execute a single hook and return the result.

    The hook receives JSON on stdin with context information.
    It should output JSON on stdout (optional) and use exit codes:
    - 0: Success (may include JSON output)
    - 2: Blocking error (stderr shown to user)
    - Other: Non-blocking error
    """
    # Build input payload
    payload = {
        "hook_event": event.value,
        "cwd": cwd or os.getcwd(),
    }

    if tool_name:
        payload["tool_name"] = tool_name
    if tool_input:
        payload["tool_input"] = tool_input
    if tool_output:
        payload["tool_output"] = tool_output

    input_json = json.dumps(payload)

    try:
        result = subprocess.run(
            hook.command,
            shell=True,
            input=input_json,
            capture_output=True,
            text=True,
            timeout=hook.timeout,
            cwd=cwd or os.getcwd(),
            env={**os.environ, "LOCO_PROJECT_DIR": cwd or os.getcwd()},
        )

        hook_result = HookResult(
            success=result.returncode == 0,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        # Parse JSON output on success
        if result.returncode == 0 and result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                if isinstance(output, dict):
                    hook_result.decision = output.get("decision")
                    hook_result.reason = output.get("reason")
                    hook_result.modified_input = output.get("modified_input")
                    hook_result.additional_context = output.get("additional_context")
            except json.JSONDecodeError:
                pass

        return hook_result

    except subprocess.TimeoutExpired:
        return HookResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Hook timed out after {hook.timeout} seconds",
        )
    except Exception as e:
        return HookResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=str(e),
        )


def execute_hooks(
    hooks: list[Hook],
    event: HookEvent,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_output: str | None = None,
    cwd: str | None = None,
) -> list[HookResult]:
    """Execute multiple hooks and return all results.

    Hooks are executed sequentially. If any hook returns a "deny" decision,
    subsequent hooks are still executed but the deny is noted.
    """
    results = []

    for hook in hooks:
        result = execute_hook(
            hook=hook,
            event=event,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            cwd=cwd,
        )
        results.append(result)

    return results


def check_pre_tool_hooks(
    hooks: list[Hook],
    tool_name: str,
    tool_input: dict[str, Any],
    cwd: str | None = None,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Check PreToolUse hooks and return whether the tool should proceed.

    Returns:
        (allowed, reason, modified_input)
        - allowed: True if tool should proceed, False if denied
        - reason: Reason for denial if denied
        - modified_input: Modified tool input if provided by hook
    """
    results = execute_hooks(
        hooks=hooks,
        event=HookEvent.PRE_TOOL_USE,
        tool_name=tool_name,
        tool_input=tool_input,
        cwd=cwd,
    )

    modified_input = None

    for result in results:
        # Check for deny decision
        if result.decision == "deny":
            return False, result.reason or result.stderr, None

        # Check for blocking error (exit code 2)
        if result.exit_code == 2:
            return False, result.stderr or "Hook blocked execution", None

        # Collect modified input (last one wins)
        if result.modified_input:
            modified_input = result.modified_input

    return True, None, modified_input


def run_post_tool_hooks(
    hooks: list[Hook],
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: str,
    cwd: str | None = None,
) -> str | None:
    """Run PostToolUse hooks and return any additional context.

    Returns:
        Additional context string to append to tool result, or None
    """
    results = execute_hooks(
        hooks=hooks,
        event=HookEvent.POST_TOOL_USE,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        cwd=cwd,
    )

    # Collect additional context from all hooks
    context_parts = []
    for result in results:
        if result.additional_context:
            context_parts.append(result.additional_context)
        elif result.stderr and not result.success:
            # Include stderr as context for failed hooks
            context_parts.append(f"[Hook warning: {result.stderr}]")

    return "\n".join(context_parts) if context_parts else None
