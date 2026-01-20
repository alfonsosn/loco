"""Chat and conversation management for loco."""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Generator

import litellm
from rich.console import Console
from rich.markdown import Markdown

# Drop unsupported params for models that don't support them (e.g., tool_choice on Bedrock Mistral)
litellm.drop_params = True

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # multiplier for exponential backoff


class APIError(Exception):
    """Raised when API call fails after retries."""
    pass

from loco.config import Config, get_provider_config
from loco.ui.components import Spinner, StreamingMarkdown, ToolPanel


@dataclass
class Message:
    """A chat message."""

    role: str  # "system", "user", "assistant", "tool"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to LiteLLM message format."""
        msg: dict[str, Any] = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name

        return msg


@dataclass
class ToolCall:
    """A parsed tool call from the LLM response."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Conversation:
    """Manages a conversation with message history."""

    messages: list[Message] = field(default_factory=list)
    model: str = ""
    config: Config | None = None
    usage: Any = None  # SessionUsage from loco.usage

    def add_system_message(self, content: str) -> None:
        """Add or update the system message."""
        # Remove existing system message if present
        self.messages = [m for m in self.messages if m.role != "system"]
        # Add new system message at the beginning
        self.messages.insert(0, Message(role="system", content=content))

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(
        self,
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add an assistant message."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))

    def add_tool_result(self, tool_call_id: str, name: str, result: str) -> None:
        """Add a tool result message."""
        self.messages.append(Message(
            role="tool",
            content=result,
            tool_call_id=tool_call_id,
            name=name,
        ))

    def get_messages(self) -> list[dict[str, Any]]:
        """Get messages in LiteLLM format."""
        return [m.to_dict() for m in self.messages]

    def clear(self) -> None:
        """Clear conversation history, keeping system message."""
        system_msg = next((m for m in self.messages if m.role == "system"), None)
        self.messages = []
        if system_msg:
            self.messages.append(system_msg)


def get_default_system_prompt(cwd: str, skills_section: str = "") -> str:
    """Get the default system prompt for loco."""
    # Get git status if in a repository
    git_info = ""
    try:
        from loco.git import get_git_status
        git_status = get_git_status()
        if git_status.is_repo:
            git_info = f"\nGit repository: Yes (branch: {git_status.branch})"
            if git_status.staged_files:
                git_info += f"\n  Staged files: {len(git_status.staged_files)}"
            if git_status.unstaged_files:
                git_info += f"\n  Unstaged files: {len(git_status.unstaged_files)}"
            if git_status.ahead:
                git_info += f"\n  Commits ahead: {git_status.ahead}"
    except Exception:
        pass

    base_prompt = f"""You are a helpful coding assistant running in a terminal. You help users with software engineering tasks.

Current working directory: {cwd}{git_info}

You have access to tools for reading, writing, and editing files, as well as running bash commands.

Guidelines:
- Be concise and direct in your responses
- When reading or modifying files, always use the appropriate tools
- Explain what you're doing when using tools
- If you're unsure about something, ask for clarification
- Format code blocks with appropriate language tags for syntax highlighting
- When showing file paths, use absolute paths when possible

Available tools:
- read: Read file contents
- write: Write content to a file (creates or overwrites)
- edit: Edit a file by replacing a specific string
- bash: Execute a bash command
- glob: Find files matching a pattern (e.g., '**/*.py')
- grep: Search file contents with regex"""

    if skills_section:
        base_prompt += f"\n{skills_section}"

    return base_prompt


def stream_response(
    conversation: Conversation,
    tools: list[dict[str, Any]] | None = None,
    console: Console | None = None,
) -> Generator[str | ToolCall, None, None]:
    """Stream a response from the LLM.

    Yields:
        str chunks for text content
        ToolCall objects when the LLM wants to call a tool
    """
    # Build kwargs for litellm
    kwargs: dict[str, Any] = {
        "model": conversation.model,
        "messages": conversation.get_messages(),
        "stream": True,
        "stream_options": {"include_usage": True},  # Request usage data in stream
    }

    # Add provider-specific config
    if conversation.config:
        provider_config = get_provider_config(conversation.model, conversation.config)
        kwargs.update(provider_config)

    # Add tools if provided
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    # Make the streaming call with retry logic
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = litellm.completion(**kwargs)
            break
        except (litellm.RateLimitError, litellm.ServiceUnavailableError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                time.sleep(delay)
                continue
            raise APIError(f"API call failed after {MAX_RETRIES} retries: {e}") from e
        except litellm.APIConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                time.sleep(delay)
                continue
            raise APIError(f"Connection error after {MAX_RETRIES} retries: {e}") from e

    # Track accumulated content and tool calls
    content_chunks: list[str] = []
    tool_calls_data: dict[int, dict[str, Any]] = {}
    usage_data: dict[str, Any] | None = None

    for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None

        if delta is None:
            continue

        # Handle content
        if delta.content:
            content_chunks.append(delta.content)
            yield delta.content

        # Handle tool calls
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_data:
                    tool_calls_data[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }

                if tc.id:
                    tool_calls_data[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tool_calls_data[idx]["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments
        
        # Capture usage data (typically in the last chunk)
        if hasattr(chunk, 'usage') and chunk.usage:
            usage_data = chunk.usage

    # After streaming, add the assistant message to conversation
    full_content = "".join(content_chunks) if content_chunks else None
    tool_calls_list = list(tool_calls_data.values()) if tool_calls_data else None

    if full_content or tool_calls_list:
        conversation.add_assistant_message(
            content=full_content,
            tool_calls=tool_calls_list,
        )
    
    # Track usage stats if available
    if usage_data:
        from loco.usage import UsageStats, SessionUsage
        
        # Initialize session usage if needed
        if conversation.usage is None:
            conversation.usage = SessionUsage()
        
        # Add this call's usage
        stat = UsageStats.from_response(
            model=conversation.model,
            usage_data=usage_data if isinstance(usage_data, dict) else {
                "prompt_tokens": getattr(usage_data, "prompt_tokens", 0),
                "completion_tokens": getattr(usage_data, "completion_tokens", 0),
                "total_tokens": getattr(usage_data, "total_tokens", 0),
            }
        )
        conversation.usage.add(stat)

    # Yield tool calls
    for tc_data in tool_calls_data.values():
        try:
            arguments = json.loads(tc_data["function"]["arguments"])
        except json.JSONDecodeError:
            arguments = {}

        yield ToolCall(
            id=tc_data["id"],
            name=tc_data["function"]["name"],
            arguments=arguments,
        )


def _display_usage_stats(conversation: Conversation, console: Console, turn_stats_only: bool = False) -> None:
    """Display usage statistics after a turn.
    
    Args:
        conversation: The conversation with usage tracking
        console: Console for output
        turn_stats_only: If True, only show the last turn's stats (not cumulative)
    """
    if not conversation.usage or conversation.usage.get_call_count() == 0:
        return
    
    usage = conversation.usage
    last_stat = usage.stats[-1]
    
    # Show per-turn stats
    console.print(
        f"\n[dim]💭 {last_stat.total_tokens:,} tokens "
        f"(in: {last_stat.prompt_tokens:,}, out: {last_stat.completion_tokens:,}) "
        f"• ${last_stat.cost:.4f}[/dim]"
    )
    
    # Show cumulative session stats if this isn't the first call
    if not turn_stats_only and usage.get_call_count() > 1:
        total_cost = usage.get_total_cost()
        total_tokens = usage.get_total_tokens()
        console.print(
            f"[dim]📊 Session: {total_tokens:,} tokens total • ${total_cost:.4f} cumulative[/dim]"
        )


def chat_turn(
    conversation: Conversation,
    user_input: str,
    tools: list[dict[str, Any]] | None,
    tool_executor: Any,  # Callable[[ToolCall], str]
    console: Console,
    hook_config: Any = None,  # HookConfig from hooks.py
) -> None:
    """Execute a single chat turn with potential tool calls.

    This handles:
    1. Adding user message
    2. Streaming LLM response
    3. Executing any tool calls (with PreToolUse/PostToolUse hooks)
    4. Continuing conversation if tools were called
    """
    from loco.ui.components import StreamingMarkdown, Spinner

    conversation.add_user_message(user_input)
    
    # Track API calls at the start to know which are new
    initial_call_count = conversation.usage.get_call_count() if conversation.usage else 0

    while True:
        # Stream the response
        tool_calls: list[ToolCall] = []
        content_buffer = ""
        first_token = True

        # Show spinner while waiting for first token
        spinner = Spinner(console, "Thinking...")
        spinner.__enter__()

        try:
            with StreamingMarkdown(console) as stream:
                for item in stream_response(conversation, tools, console):
                    # Hide spinner on first content
                    if first_token:
                        spinner.__exit__(None, None, None)
                        first_token = False

                    if isinstance(item, str):
                        content_buffer += item
                        stream.append(item)
                    elif isinstance(item, ToolCall):
                        tool_calls.append(item)
        finally:
            # Ensure spinner is closed if no content received
            if first_token:
                spinner.__exit__(None, None, None)

        # If no tool calls, we're done - show final usage
        if not tool_calls:
            _display_usage_stats(conversation, console)
            break

        # Execute tool calls
        for tc in tool_calls:
            tool_input = tc.arguments

            # Run PreToolUse hooks if configured
            if hook_config:
                from loco.hooks import HookEvent, check_pre_tool_hooks
                pre_hooks = hook_config.get_hooks(HookEvent.PRE_TOOL_USE, tc.name)
                if pre_hooks:
                    allowed, reason, modified_input = check_pre_tool_hooks(
                        hooks=pre_hooks,
                        tool_name=tc.name,
                        tool_input=tool_input,
                    )
                    if not allowed:
                        # Hook denied the tool call
                        ToolPanel.tool_call(tc.name, tool_input, console)
                        result = f"[Hook blocked]: {reason or 'Denied by hook'}"
                        ToolPanel.tool_result(tc.name, result, False, console)
                        conversation.add_tool_result(tc.id, tc.name, result)
                        continue
                    if modified_input:
                        tool_input = modified_input

            ToolPanel.tool_call(tc.name, tool_input, console)

            try:
                # Create a modified ToolCall with potentially updated arguments
                modified_tc = ToolCall(id=tc.id, name=tc.name, arguments=tool_input)
                result = tool_executor(modified_tc)
                success = True
            except Exception as e:
                result = f"Error: {e}"
                success = False

            # Run PostToolUse hooks if configured
            if hook_config and success:
                from loco.hooks import HookEvent, run_post_tool_hooks
                post_hooks = hook_config.get_hooks(HookEvent.POST_TOOL_USE, tc.name)
                if post_hooks:
                    additional_context = run_post_tool_hooks(
                        hooks=post_hooks,
                        tool_name=tc.name,
                        tool_input=tool_input,
                        tool_output=result,
                    )
                    if additional_context:
                        result = f"{result}\n\n{additional_context}"

            ToolPanel.tool_result(tc.name, result, success, console)

            # Add tool result to conversation
            conversation.add_tool_result(tc.id, tc.name, result)

        # Continue the loop to get the LLM's response to tool results
