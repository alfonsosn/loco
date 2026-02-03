"""CLI entry point for loco."""

import os
import sys
import subprocess
from pathlib import Path

import click
from rich.console import Console as RichConsole

from loco import __version__
from loco.chat import Conversation, ToolCall, chat_turn, get_default_system_prompt
from loco.config import (
    Config,
    get_config_path,
    load_config,
    resolve_model,
    save_config,
)
from loco.tools import tool_registry
from loco.ui.console import get_console, Console
from loco.history import save_conversation, load_conversation, list_sessions
from loco.commands import command_registry, get_commands_system_prompt_section, Command
from loco.hooks import HookConfig
from loco.agents import agent_registry, run_agent
from loco.planner import (
    create_plan, save_plan, load_plan, list_plans,
    format_plan_for_display, PLANNING_SYSTEM_PROMPT,
    PlanStatus, StepStatus,
)
from loco.git import (
    get_git_status, get_all_diff, get_staged_diff,
    generate_commit_message_prompt, generate_pr_description_prompt,
    get_commit_history, get_branch_diff, get_current_branch,
    create_commit, stage_all_changes,
)
from loco.telemetry import get_tracker, CostTracker, CostProfile
from loco.rewind import RewindManager, set_rewind_manager, get_rewind_manager


# Track current session ID for auto-save
_current_session_id: str | None = None

# Track active command for current conversation
_active_command: Command | None = None


def _display_cost_profile(console: Console, profile: CostProfile) -> None:
    """Display cost profile dashboard."""
    from rich.table import Table
    from rich.panel import Panel
    from datetime import datetime

    duration = datetime.now() - profile.start_time
    duration_str = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"

    # Header panel
    header = f"""[bold]Session:[/bold] {profile.session_id}  [bold]Duration:[/bold] {duration_str}
[bold]Total Cost:[/bold] ${profile.total_cost:.4f}
[bold]Tokens:[/bold] In: {profile.total_input_tokens:,}  Out: {profile.total_output_tokens:,}  Cache Read: {profile.total_cache_read:,}  Cache Write: {profile.total_cache_write:,}"""

    console.print(Panel(header, title="LOCO Cost Profile", border_style="blue"))

    # Cost by operation
    console.print("\n[bold]Cost by Operation:[/bold]")
    op_costs = profile.cost_by_operation()
    total = profile.total_cost or 1  # avoid division by zero

    for op, cost in list(op_costs.items())[:8]:  # top 8
        pct = (cost / total) * 100
        bar_len = int(pct / 5)  # scale to ~20 chars max
        bar = "[green]" + "█" * bar_len + "░" * (20 - bar_len) + "[/green]"
        console.print(f"  {op:24} {bar} ${cost:.4f} ({pct:.1f}%)")

    # Cost by agent
    agent_costs = profile.cost_by_agent()
    if len(agent_costs) > 1:  # only show if multiple agents
        console.print("\n[bold]Cost by Agent:[/bold]")
        for agent, cost in list(agent_costs.items())[:5]:
            pct = (cost / total) * 100
            console.print(f"  {agent:24} ${cost:.4f} ({pct:.1f}%)")

    # Duplicate file reads
    duplicates = profile.duplicate_file_reads()
    if duplicates:
        console.print("\n[bold yellow]Duplicate File Reads (potential waste):[/bold yellow]")
        wasted = 0
        for path, count in duplicates[:5]:
            console.print(f"  {path}: read {count}x")
            wasted += count - 1
        console.print(f"  [yellow]Total duplicate reads: {wasted}[/yellow]")

    console.print(f"\n[dim]LLM calls tracked: {len(profile.calls)}[/dim]")


def handle_slash_command(
    command: str,
    conversation: Conversation,
    config: Config,
    console: Console,
) -> bool:
    """Handle slash commands. Returns True if command was handled."""
    global _current_session_id, _active_command

    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        console.print("""
[bold]Available Commands:[/bold]

  [cyan]/help[/cyan]             Show this help message
  [cyan]/clear[/cyan]            Clear conversation history
  [cyan]/compact[/cyan]          Summarize conversation to reduce token usage
  [cyan]/model[/cyan] [name]     Show or switch the current model
  [cyan]/command[/cyan] [name]   Activate a command or list available commands
  [cyan]/commands[/cyan]         List all available commands
  [cyan]/agent[/cyan] <name> <task>  Run a subagent with a task
  [cyan]/agents[/cyan]           List all available agents
  [cyan]/save[/cyan] [name]      Save current conversation
  [cyan]/load[/cyan] <id>        Load a saved conversation
  [cyan]/sessions[/cyan]         List saved sessions
  [cyan]/stats[/cyan]            Show token usage and cost statistics
  [cyan]/context[/cyan]          Show context window usage and estimates
  [cyan]/plan[/cyan] <task>      Create a step-by-step plan for a task
  [cyan]/profile[/cyan] [on|off|save|report]  Cost profiling dashboard
  [cyan]/turns[/cyan]            List conversation turns (for REWIND)
  [cyan]/rewind[/cyan] [n]       Rewind to turn N (interactive if no argument)
  [cyan]/config[/cyan]           Show configuration file path
  [cyan]/quit[/cyan]             Exit loco (or Ctrl+C)

[bold]Input Modes:[/bold]
  Press [cyan]Shift+Tab[/cyan] to cycle between input modes:
    • [cyan]Chat mode[/cyan] ([cyan]>[/cyan]): Talk to the AI assistant
    • [cyan]Bash mode[/cyan] ([yellow]![/yellow]): Execute shell commands directly

  You can also prefix commands with [cyan]![/cyan] in chat mode for one-off bash commands
  Examples: [cyan]! ls -la[/cyan], [cyan]! git status[/cyan], [cyan]! pwd[/cyan]

[bold]Custom Commands:[/bold]
  Commands can be invoked directly via [cyan]/<command-name>[/cyan]
  Examples: [cyan]/commit[/cyan], [cyan]/pr[/cyan] (if commands are installed)
  Use [cyan]/commands[/cyan] to see all available commands

[bold]Tips:[/bold]
- Use model aliases from config (e.g., /model gpt4)
- Or use full LiteLLM model strings (e.g., /model openai/gpt-4o)
- Commands are loaded from .loco/commands/, .claude/commands/, and ~/.config/loco/commands/
- Agents are loaded from .loco/agents/, .claude/agents/, and ~/.config/loco/agents/
""")
        return True

    elif cmd == "/clear":
        conversation.clear()
        conversation.usage = None
        _current_session_id = None
        _active_command = None
        # Reset rewind state
        rewind_manager = get_rewind_manager()
        if rewind_manager:
            rewind_manager.cleanup()
            set_rewind_manager(None)
        console.print("[dim]Conversation cleared.[/dim]")
        return True

    elif cmd == "/compact":
        from loco.usage import estimate_conversation_tokens
        from loco.chat import stream_response

        # Check if there's enough conversation to compact
        non_system_messages = [m for m in conversation.messages if m.role != "system"]
        if len(non_system_messages) < 4:
            console.print("[yellow]Not enough conversation history to compact.[/yellow]")
            console.print("[dim]Need at least 4 messages (2 exchanges). Use /clear to reset instead.[/dim]")
            return True

        # Show current state
        current_tokens = estimate_conversation_tokens(conversation)
        console.print(f"[bold]Compact Conversation[/bold]\n")
        console.print(f"  Current messages: {len(non_system_messages)} messages")
        console.print(f"  Estimated tokens: {current_tokens:,} tokens")
        console.print()
        console.print("[yellow]This will summarize the conversation to reduce token usage.[/yellow]")
        console.print("[dim]The last 2 messages will be preserved for context.[/dim]")
        console.print()
        console.print("[bold]Continue?[/bold] [dim](yes/no)[/dim]")

        response, _ = console.get_input("> ")
        if not response or response.lower() not in ["yes", "y"]:
            console.print("[dim]Compaction cancelled.[/dim]")
            return True

        console.print()
        console.print("[dim]Generating summary...[/dim]")

        # Create a temporary conversation for compaction
        compact_conv = Conversation(model=conversation.model, config=config)

        # Build compaction prompt
        messages_to_compact = non_system_messages[:-2] if len(non_system_messages) > 2 else non_system_messages

        # Format conversation history
        history = []
        for msg in messages_to_compact:
            role_label = msg.role.upper()
            content = msg.content or ""

            if msg.tool_calls:
                import json
                content += f"\n[Used tools: {json.dumps(msg.tool_calls)}]"

            history.append(f"{role_label}: {content[:500]}")  # Limit each message to 500 chars

        conversation_text = "\n\n".join(history)

        compact_prompt = f"""I need you to create a concise summary of this conversation that preserves all essential context for continuing our work.

CONVERSATION TO SUMMARIZE:
{conversation_text}

Please create a summary that includes:
1. Key decisions and conclusions reached
2. Files that were created, modified, or discussed (with paths)
3. Technical implementations completed
4. Current state of the work
5. Any open questions or next steps

Omit:
- Lengthy explanations that are no longer relevant
- Intermediate steps that led to final decisions
- Verbose descriptions (keep it factual and concise)

Format the summary as a clear, organized narrative that I can use to continue the conversation effectively."""

        compact_conv.add_user_message(compact_prompt)

        # Get summary from LLM
        try:
            summary = ""
            with console.console.status("[dim]Summarizing...[/dim]"):
                for item in stream_response(compact_conv, tools=None):
                    if isinstance(item, str):
                        summary += item

            if not summary:
                console.print("[red]Failed to generate summary.[/red]")
                return True

            # Replace conversation history
            system_msg = next((m for m in conversation.messages if m.role == "system"), None)
            last_messages = non_system_messages[-2:] if len(non_system_messages) > 2 else []

            conversation.messages = []

            # Add back system message
            if system_msg:
                conversation.messages.append(system_msg)

            # Add compacted summary as assistant message
            from loco.chat import Message
            conversation.messages.append(Message(
                role="assistant",
                content=f"[Previous conversation summary]\n\n{summary}\n\n[End of summary - continuing from here]"
            ))

            # Add back last 2 messages for immediate context
            for msg in last_messages:
                conversation.messages.append(msg)

            # Calculate new token count
            new_tokens = estimate_conversation_tokens(conversation)
            saved_tokens = current_tokens - new_tokens
            saved_percent = (saved_tokens / current_tokens * 100) if current_tokens > 0 else 0

            console.print()
            console.print(f"[green]✓[/green] Conversation compacted successfully")
            console.print(f"  New messages: {len([m for m in conversation.messages if m.role != 'system'])} messages")
            console.print(f"  New estimated tokens: {new_tokens:,} tokens")
            console.print(f"  Saved: [green]{saved_tokens:,}[/green] tokens ([green]{saved_percent:.1f}%[/green] reduction)")

        except Exception as e:
            console.print(f"[red]Error during compaction: {e}[/red]")

        return True

    elif cmd == "/model":
        if args:
            # Switch model
            new_model = resolve_model(args, config)
            conversation.model = new_model
            console.print(f"[dim]Switched to model: {new_model}[/dim]")
        else:
            # Show current model
            console.print(f"[dim]Current model: {conversation.model}[/dim]")
            console.print("\n[dim]Available aliases:[/dim]")
            for alias, model in config.models.items():
                marker = " [green]<-- current[/green]" if model == conversation.model else ""
                console.print(f"  [cyan]{alias}[/cyan]: {model}{marker}")
        return True

    elif cmd == "/save":
        name = args if args else None
        session_id = save_conversation(conversation, _current_session_id, name)
        _current_session_id = session_id
        console.print(f"[dim]Saved as session: {session_id}[/dim]")
        return True

    elif cmd == "/load":
        if not args:
            console.print("[yellow]Usage: /load <session_id>[/yellow]")
            console.print("[dim]Use /sessions to see available sessions[/dim]")
            return True

        loaded = load_conversation(args)
        if loaded is None:
            console.print(f"[red]Session not found: {args}[/red]")
            return True

        # Replace conversation content
        conversation.messages = loaded.messages
        if loaded.model:
            conversation.model = loaded.model
        if loaded.usage:
            conversation.usage = loaded.usage
        _current_session_id = args

        # Try to load rewind state if it exists
        loaded_rewind = RewindManager.load(args)
        if loaded_rewind:
            set_rewind_manager(loaded_rewind)
            console.print(f"[dim]Loaded session: {args} ({len(conversation.messages)} messages, {loaded_rewind.state.current_turn} turns)[/dim]")
        else:
            set_rewind_manager(None)
            console.print(f"[dim]Loaded session: {args} ({len(conversation.messages)} messages)[/dim]")
        return True

    elif cmd == "/sessions":
        sessions = list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions found.[/dim]")
            return True

        console.print("[bold]Saved Sessions:[/bold]\n")
        for s in sessions:
            name_str = f" ({s['name']})" if s.get('name') else ""
            console.print(
                f"  [cyan]{s['session_id']}[/cyan]{name_str} - "
                f"{s['message_count']} msgs, {s.get('model', 'unknown')}"
            )
        return True
    
    elif cmd == "/stats":
        if conversation.usage is None or conversation.usage.get_call_count() == 0:
            console.print("[dim]No usage data yet. Make some API calls first![/dim]")
            return True
        
        usage = conversation.usage
        console.print("[bold]Session Statistics:[/bold]\n")
        console.print(f"  Model: [cyan]{conversation.model}[/cyan]")
        console.print(f"  API Calls: {usage.get_call_count()}")
        console.print(f"  Total Tokens: {usage.get_total_tokens():,}")
        console.print(f"    • Input: {usage.get_prompt_tokens():,} tokens")
        console.print(f"    • Output: {usage.get_completion_tokens():,} tokens")
        console.print(f"  Estimated Cost: [green]${usage.get_total_cost():.4f}[/green]")
        
        # Show per-call breakdown if there are multiple calls
        if usage.get_call_count() > 1:
            console.print("\n[dim]Recent calls:[/dim]")
            for i, stat in enumerate(usage.stats[-5:], start=max(1, len(usage.stats) - 4)):
                console.print(
                    f"    {i}. {stat.total_tokens:,} tokens → ${stat.cost:.4f}"
                )
        
        console.print("\n[dim]Note: Costs are estimates based on standard pricing[/dim]")
        return True

    elif cmd == "/context":
        from loco.usage import get_model_context_window, estimate_conversation_tokens

        console.print("[bold]Context Usage[/bold]\n")
        console.print(f"  Model: [cyan]{conversation.model}[/cyan]")

        # Get context window
        context_window = get_model_context_window(conversation.model)
        if context_window:
            console.print(f"  Context Window: [cyan]{context_window:,}[/cyan] tokens")
        else:
            console.print(f"  Context Window: [yellow]Unknown[/yellow]")

        console.print()

        # Estimate current conversation tokens
        estimated_tokens = estimate_conversation_tokens(conversation)

        # Calculate message breakdown
        system_tokens = 0
        message_tokens = 0

        for msg in conversation.messages:
            if msg.role == "system":
                if msg.content:
                    system_tokens += len(msg.content) // 4
            else:
                if msg.content:
                    message_tokens += len(msg.content) // 4
                if msg.tool_calls:
                    import json
                    message_tokens += len(json.dumps(msg.tool_calls)) // 4

        # Add overhead
        system_tokens += 15  # Format overhead
        message_tokens += (len([m for m in conversation.messages if m.role != "system"]) * 15)

        console.print("  [bold]Current Conversation:[/bold]")
        console.print(f"    • System Prompt: [cyan]{system_tokens:,}[/cyan] tokens")
        console.print(f"    • Messages: [cyan]{message_tokens:,}[/cyan] tokens")
        console.print(f"    • Total Estimated: [cyan]{estimated_tokens:,}[/cyan] tokens", end="")

        # Show percentage if we know the context window
        if context_window:
            percentage = (estimated_tokens / context_window) * 100
            remaining = context_window - estimated_tokens

            # Color code based on usage
            if percentage >= 80:
                percent_color = "red"
                status = "⚠️"
            elif percentage >= 60:
                percent_color = "yellow"
                status = ""
            else:
                percent_color = "green"
                status = ""

            console.print(f" [{percent_color}]({percentage:.1f}%)[/{percent_color}] {status}")
            console.print(f"    • Remaining: [cyan]{remaining:,}[/cyan] tokens [{percent_color}]({100-percentage:.1f}%)[/{percent_color}]")

            if percentage >= 80:
                console.print()
                console.print("  [yellow]⚠️  Warning: Approaching context window limit[/yellow]")
                console.print("  [dim]Consider using /clear to reset the conversation[/dim]")
        else:
            console.print()

        console.print()
        console.print("[dim]Note: Token estimates are approximate and may vary from actual usage[/dim]")
        return True

    elif cmd == "/plan":
        if not args:
            console.print("[yellow]Usage: /plan <task description>[/yellow]")
            console.print("[dim]Example: /plan Add user authentication with JWT[/dim]")
            return True

        task = args
        console.print(f"[bold]Creating plan for:[/bold] {task}\n")
        console.print("[dim]Analyzing codebase and generating steps...[/dim]")

        # Create a planning conversation
        planning_conv = Conversation(
            model=conversation.model,
            config=conversation.config,
        )
        planning_conv.add_system_message(PLANNING_SYSTEM_PROMPT)
        planning_conv.add_user_message(
            f"Task: {task}\n\n"
            f"Working directory: {os.getcwd()}\n\n"
            "Analyze the codebase and create a detailed step-by-step plan for this task."
        )

        # Get plan from LLM
        try:
            plan_text = ""
            with console.console.status("[dim]Planning...[/dim]"):
                from loco.chat import stream_response
                for item in stream_response(planning_conv, tools=tool_registry.get_openai_tools()):
                    if isinstance(item, str):
                        plan_text += item

            # Parse steps from response (expecting numbered list)
            steps = []
            for line in plan_text.split("\n"):
                line = line.strip()
                # Match "1. Step description" or "1) Step description"
                import re
                match = re.match(r"^\d+[\.)]\s+(.+)$", line)
                if match:
                    steps.append(match.group(1))

            if not steps:
                console.print("[red]Failed to generate plan steps[/red]")
                return True

            # Create and save plan
            plan = create_plan(task, steps)
            save_plan(plan)

            # Display plan
            console.print("\n" + format_plan_for_display(plan))
            console.print(f"\n[dim]Plan saved as: {plan.id}[/dim]")
            console.print("\n[bold]Approve this plan?[/bold] [dim](yes/no)[/dim]")

            # Get user approval
            approval, _ = console.get_input("> ")
            if approval and approval.lower() in ["yes", "y"]:
                plan.status = PlanStatus.APPROVED
                plan.status = PlanStatus.EXECUTING
                save_plan(plan)

                console.print("[green]Plan approved! Executing steps...[/green]\n")

                # Execute each step
                for step in plan.steps:
                    step.status = StepStatus.IN_PROGRESS
                    save_plan(plan)

                    console.print(f"[yellow]●[/yellow] Executing: {step.description}")

                    # Add step to conversation and execute
                    try:
                        chat_turn(
                            conversation=conversation,
                            user_input=f"Execute this step: {step.description}",
                            tools=tool_registry.get_openai_tools(),
                            tool_executor=tool_executor,
                            console=console.console,
                            hook_config=HookConfig.from_dict(config.hooks) if config.hooks else None,
                        )
                        step.status = StepStatus.COMPLETED
                        console.print(f"[green]✓[/green] Completed: {step.description}\n")
                    except Exception as e:
                        step.status = StepStatus.FAILED
                        step.error = str(e)
                        console.print(f"[red]✗[/red] Failed: {step.description}")
                        console.print(f"[red]Error: {e}[/red]\n")

                        console.print("[yellow]Continue with remaining steps?[/yellow] [dim](yes/no)[/dim]")
                        continue_resp, _ = console.get_input("> ")
                        if not continue_resp or continue_resp.lower() not in ["yes", "y"]:
                            break

                    save_plan(plan)

                plan.status = PlanStatus.COMPLETED
                save_plan(plan)
                console.print("[green]Plan execution completed![/green]")
            else:
                console.print("[dim]Plan cancelled.[/dim]")

        except Exception as e:
            console.print(f"[red]Error creating plan: {e}[/red]")

        return True

    elif cmd in ("/command", "/commands"):
        commands = command_registry.get_user_invocable()

        if not args or cmd == "/commands":
            # List available commands
            if not commands:
                console.print("[dim]No commands found.[/dim]")
                console.print("[dim]Add commands to .loco/commands/, .claude/commands/, or ~/.config/loco/commands/[/dim]")
                return True

            console.print("[bold]Available Commands:[/bold]\n")
            for command in commands:
                active_marker = " [green]<-- active[/green]" if _active_command and _active_command.name == command.name else ""
                console.print(f"  [cyan]{command.name}[/cyan]: {command.description}{active_marker}")

            if _active_command:
                console.print(f"\n[dim]Active command: {_active_command.name}[/dim]")
                console.print("[dim]Use /command off to deactivate[/dim]")
            return True

        # Activate or deactivate a command
        if args.lower() == "off":
            if _active_command:
                console.print(f"[dim]Deactivated command: {_active_command.name}[/dim]")
                _active_command = None
                # Rebuild system prompt without command
                conversation.add_system_message(
                    get_default_system_prompt(os.getcwd(), get_commands_system_prompt_section())
                )
            else:
                console.print("[dim]No active command to deactivate[/dim]")
            return True

        # Find and activate the command
        command = command_registry.get(args)
        if command is None:
            console.print(f"[red]Command not found: {args}[/red]")
            console.print("[dim]Use /commands to see available commands[/dim]")
            return True

        _active_command = command
        # Update system prompt with command content
        commands_section = get_commands_system_prompt_section()
        commands_section += command.get_system_prompt_addition()
        conversation.add_system_message(
            get_default_system_prompt(os.getcwd(), commands_section)
        )
        console.print(f"[dim]Activated command: {command.name}[/dim]")
        return True

    elif cmd in ("/agent", "/agents"):
        agents = agent_registry.get_all()

        if cmd == "/agents" or not args:
            # List available agents
            if not agents:
                console.print("[dim]No agents found.[/dim]")
                console.print("[dim]Add agents to .loco/agents/, .claude/agents/, or ~/.config/loco/agents/[/dim]")
                return True

            console.print("[bold]Available Agents:[/bold]\n")
            for agent in agents:
                tools_info = ""
                if agent.allowed_tools:
                    tools_info = f" [dim](tools: {', '.join(agent.allowed_tools)})[/dim]"
                console.print(f"  [cyan]{agent.name}[/cyan]: {agent.description}{tools_info}")

            console.print("\n[dim]Usage: /agent <name> <task>[/dim]")
            return True

        # Parse agent name and task
        agent_parts = args.split(maxsplit=1)
        agent_name = agent_parts[0]
        task = agent_parts[1] if len(agent_parts) > 1 else ""

        if not task:
            console.print("[yellow]Usage: /agent <name> <task>[/yellow]")
            console.print("[dim]Example: /agent explorer find all API endpoints[/dim]")
            return True

        # Find the agent
        agent = agent_registry.get(agent_name)
        if agent is None:
            console.print(f"[red]Agent not found: {agent_name}[/red]")
            console.print("[dim]Use /agents to see available agents[/dim]")
            return True

        # Run the agent
        try:
            result = run_agent(
                agent=agent,
                task=task,
                config=config,
                tool_registry=tool_registry,
                console=console,
            )
            # Add a summary to the main conversation
            conversation.add_user_message(f"[Agent '{agent_name}' completed task: {task}]")
            conversation.add_assistant_message(f"Agent result:\n\n{result}")
        except Exception as e:
            console.print(f"[red]Agent error: {e}[/red]")

        return True

    elif cmd == "/profile":
        tracker = get_tracker()
        args_list = args.split() if args else []

        if args_list and args_list[0] == "on":
            tracker.enable()
            console.print("[green]Cost profiling enabled[/green]")
            return True
        elif args_list and args_list[0] == "off":
            tracker.disable()
            console.print("[yellow]Cost profiling disabled[/yellow]")
            return True
        elif args_list and args_list[0] == "save":
            path = tracker.save_profile(Path.home() / ".config" / "loco" / "profiles")
            if path:
                console.print(f"[green]Profile saved to {path}[/green]")
            return True
        elif args_list and args_list[0] == "report":
            from loco.telemetry import generate_report
            profile = tracker.profile
            if profile is None:
                console.print("[yellow]No profile data[/yellow]")
                return True

            report = generate_report(profile)

            # Save to file if path provided
            if len(args_list) > 1:
                path = Path(args_list[1])
                path.write_text(report)
                console.print(f"[green]Report saved to {path}[/green]")
            else:
                console.print(report)
            return True

        if not tracker.enabled:
            console.print("[yellow]Cost profiling is not enabled.[/yellow]")
            console.print("Run with --profile flag or use /profile on")
            return True

        profile = tracker.profile
        if profile is None or not profile.calls:
            console.print("[yellow]No data yet. Make some LLM calls first.[/yellow]")
            return True

        # Display dashboard
        _display_cost_profile(console, profile)
        return True

    elif cmd == "/config":
        console.print(f"[dim]Config file: {get_config_path()}[/dim]")
        return True

    elif cmd == "/turns":
        rewind_manager = get_rewind_manager()
        if not rewind_manager:
            console.print("[yellow]REWIND is not enabled for this session.[/yellow]")
            console.print("[dim]Enable with rewind.enabled = true in config[/dim]")
            return True

        if rewind_manager.state.current_turn == 0:
            console.print("[dim]No turns recorded yet.[/dim]")
            return True

        console.print("[bold]Conversation Turns:[/bold]\n")
        for checkpoint in rewind_manager.state.checkpoints:
            # Format turn info
            summary = checkpoint.summary or "[No summary]"
            if len(summary) > 60:
                summary = summary[:57] + "..."

            current_marker = " [green]← current[/green]" if checkpoint.turn_number == rewind_manager.state.current_turn else ""
            files_changed = len(checkpoint.file_changes)
            files_info = f" [dim]({files_changed} file{'s' if files_changed != 1 else ''} changed)[/dim]" if files_changed > 0 else ""

            console.print(f"  [cyan]Turn {checkpoint.turn_number}:[/cyan] {summary}{files_info}{current_marker}")

        # Show modified files summary
        all_files = set()
        for checkpoint in rewind_manager.state.checkpoints:
            for change in checkpoint.file_changes:
                all_files.add(change.path)

        if all_files:
            console.print(f"\n[dim]Files modified this session: {', '.join(sorted(all_files)[:5])}")
            if len(all_files) > 5:
                console.print(f"  ... and {len(all_files) - 5} more[/dim]")
            else:
                console.print("[/dim]", end="")

        console.print("\n[dim]Use /rewind <n> to rewind to turn N[/dim]")
        return True

    elif cmd == "/rewind":
        rewind_manager = get_rewind_manager()
        if not rewind_manager:
            console.print("[yellow]REWIND is not enabled for this session.[/yellow]")
            console.print("[dim]Enable with rewind.enabled = true in config[/dim]")
            return True

        if rewind_manager.state.current_turn == 0:
            console.print("[dim]No turns to rewind to.[/dim]")
            return True

        # Handle subcommands
        if args == "cleanup":
            # Cleanup rewind state
            console.print("[bold]Clean up REWIND storage?[/bold]")
            console.print(f"[dim]This will remove all snapshots for session {rewind_manager.state.session_id}[/dim]")
            console.print("\n[bold]Continue?[/bold] [dim](yes/no)[/dim]")

            response, _ = console.get_input("> ")
            if response and response.lower() in ["yes", "y"]:
                rewind_manager.cleanup()
                console.print("[green]✓[/green] REWIND storage cleaned up")
            else:
                console.print("[dim]Cancelled.[/dim]")
            return True

        # Parse turn number
        target_turn = None
        if args:
            try:
                target_turn = int(args)
            except ValueError:
                console.print(f"[red]Invalid turn number: {args}[/red]")
                console.print("[dim]Usage: /rewind <turn_number> or /rewind cleanup[/dim]")
                return True
        else:
            # Interactive mode - show turns and ask
            console.print("[bold]Rewind to which turn?[/bold]\n")
            for checkpoint in rewind_manager.state.checkpoints:
                summary = checkpoint.summary or "[No summary]"
                if len(summary) > 50:
                    summary = summary[:47] + "..."
                current_marker = " [green]← current[/green]" if checkpoint.turn_number == rewind_manager.state.current_turn else ""
                console.print(f"  [{checkpoint.turn_number}] {summary}{current_marker}")

            console.print(f"\n  [0] Beginning (before any changes)")
            console.print("\nEnter turn number (or 'cancel'):")

            response, _ = console.get_input("> ")
            if not response or response.lower() in ["cancel", "c"]:
                console.print("[dim]Cancelled.[/dim]")
                return True

            try:
                target_turn = int(response)
            except ValueError:
                console.print("[red]Invalid turn number.[/red]")
                return True

        # Validate turn number
        if target_turn < 0 or target_turn > rewind_manager.state.current_turn:
            console.print(f"[red]Invalid turn number. Valid range: 0-{rewind_manager.state.current_turn}[/red]")
            return True

        if target_turn == rewind_manager.state.current_turn:
            console.print("[dim]Already at turn {target_turn}.[/dim]")
            return True

        # Check for conflicts
        conflicts = rewind_manager.validate_before_rewind(target_turn)
        if conflicts:
            console.print("[yellow]Warning: Some files have been modified outside of loco:[/yellow]")
            for conflict in conflicts[:5]:
                console.print(f"  • {conflict.path}")
            if len(conflicts) > 5:
                console.print(f"  ... and {len(conflicts) - 5} more")

            console.print("\n[bold]Overwrite these files?[/bold] [dim](yes/no)[/dim]")
            response, _ = console.get_input("> ")
            if not response or response.lower() not in ["yes", "y"]:
                console.print("[dim]Rewind cancelled.[/dim]")
                return True

        # Perform rewind
        console.print(f"\n[bold]Rewinding to turn {target_turn}...[/bold]")
        success, restored_files, _ = rewind_manager.rewind_to_turn(target_turn, force=True)

        if success:
            for msg in restored_files:
                console.print(f"  {msg}")

            # Truncate conversation
            message_index = rewind_manager.get_message_index_for_turn(target_turn)
            if message_index is not None and message_index < len(conversation.messages):
                # Keep system message and truncate the rest
                system_msg = next((m for m in conversation.messages if m.role == "system"), None)
                conversation.messages = conversation.messages[:message_index]
                if system_msg and (not conversation.messages or conversation.messages[0].role != "system"):
                    conversation.messages.insert(0, system_msg)

            console.print(f"\n[green]✓[/green] Rewound to turn {target_turn}")
            if target_turn == 0:
                console.print("[dim]All file changes have been undone.[/dim]")
        else:
            console.print("[red]Rewind failed.[/red]")

        return True

    elif cmd in ("/quit", "/exit", "/q"):
        console.print("[dim]Goodbye![/dim]")
        sys.exit(0)

    # Check if command matches a custom command (e.g., /commit, /pr)
    command_name = cmd[1:]  # Remove leading slash
    custom_command = command_registry.get(command_name)
    if custom_command and custom_command.user_invocable:
        # Execute command one-shot style
        from loco.chat import stream_response

        # Create temporary conversation for command execution
        command_conv = Conversation(model=conversation.model, config=conversation.config)

        # Add command instructions as system message
        command_conv.add_system_message(custom_command.content)

        # Add any args as user message
        if args:
            command_conv.add_user_message(args)
        else:
            # Add empty user message to trigger execution
            command_conv.add_user_message("Execute the command instructions.")

        try:
            # Execute command
            for item in stream_response(command_conv, tools=tool_registry.get_all()):
                if isinstance(item, str):
                    console.print(item, end="")
                elif isinstance(item, ToolCall):
                    # Execute tool
                    result = tool_executor(item)
                    command_conv.add_tool_result(item.id, result)

            console.print()  # Final newline
        except Exception as e:
            console.print(f"\n[red]Error executing command: {e}[/red]")

        return True

    return False


def tool_executor(tool_call: ToolCall) -> str:
    """Execute a tool call and return the result."""
    return tool_registry.execute(tool_call.name, tool_call.arguments)


@click.group(invoke_without_command=True)
@click.option(
    "--model", "-m",
    help="Model to use (alias or full LiteLLM model string)",
)
@click.option(
    "--cwd", "-C",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Working directory",
)
@click.option(
    "--bash", "-b",
    is_flag=True,
    help="Start in bash mode (use Shift+Tab to cycle modes)",
)
@click.option(
    "--profile",
    is_flag=True,
    help="Enable cost profiling",
)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context, model: str | None, cwd: str | None, bash: bool, profile: bool) -> None:
    """Loco - LLM Coding Assistant CLI.

    An AI-powered coding assistant that works with any OpenAI-compatible LLM.

    Supports multiple interaction modes:
    - Regular chat: Just type your message
    - Bash commands: Prefix with ! (e.g., ! ls -la)
    - Slash commands: Use / for special commands (e.g., /help, /commit)
    """
    # If a subcommand is invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return

    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)

    # Enable profiling if flag is set
    if profile:
        tracker = get_tracker()
        tracker.enable()

    # Change working directory if specified
    if cwd:
        os.chdir(cwd)

    # Resolve model
    effective_model = resolve_model(model or config.default_model, config)

    # Discover commands and agents
    command_registry.discover()
    agent_registry.discover()
    commands_section = get_commands_system_prompt_section()

    # Initialize UI
    console = get_console()
    rich_console = console.console

    # Set initial mode based on --bash flag
    if bash:
        from loco.ui.console import InputMode
        console.current_mode = InputMode.BASH

    # Print welcome
    console.print_welcome(effective_model, os.getcwd())

    # Show discovered commands and agents count
    command_count = len(command_registry.get_all())
    agent_count = len(agent_registry.get_all())
    info_parts = []
    if command_count > 0:
        info_parts.append(f"{command_count} command(s)")
    if agent_count > 0:
        info_parts.append(f"{agent_count} agent(s)")
    if info_parts:
        console.print(f"[dim]{', '.join(info_parts)} available.[/dim]\n")

    # Initialize conversation
    conversation = Conversation(
        model=effective_model,
        config=config,
    )
    conversation.add_system_message(get_default_system_prompt(os.getcwd(), commands_section))

    # Initialize REWIND manager if enabled
    global _current_session_id
    if config.rewind.enabled:
        from loco.history import generate_session_id
        _current_session_id = generate_session_id()
        rewind_manager = RewindManager.initialize(
            session_id=_current_session_id,
            working_directory=os.getcwd(),
        )
        set_rewind_manager(rewind_manager)

    # Get tools
    tools = tool_registry.get_openai_tools()

    # Initialize hooks
    hook_config = HookConfig.from_dict(config.hooks) if config.hooks else None

    # Main loop
    while True:
        try:
            # Get input and current mode
            user_input, mode = console.get_input()

            if user_input is None:
                # Ctrl+C or Ctrl+D
                console.print("\n[dim]Goodbye![/dim]")
                break

            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle slash commands first (works in all modes)
            if user_input.startswith("/"):
                if handle_slash_command(user_input, conversation, config, console):
                    continue
                else:
                    console.print_error(f"Unknown command: {user_input.split()[0]}")
                    console.print("[dim]Type /help for available commands[/dim]")
                    continue

            # Import InputMode to check current mode
            from loco.ui.console import InputMode

            # Handle bash mode - execute input as bash command
            if mode == InputMode.BASH:
                if not user_input:
                    console.print("[yellow]Enter a bash command[/yellow]")
                    console.print("[dim]Example: ls -la[/dim]")
                    console.print("[dim]Press Shift+Tab to switch back to chat mode[/dim]")
                    continue

                try:
                    # Execute bash command and capture output
                    result = subprocess.run(
                        user_input,
                        shell=True,
                        capture_output=True,
                        text=True,
                        check=False  # Don't raise exception on non-zero exit codes
                    )

                    # Show output
                    if result.stdout:
                        console.print(result.stdout, end="")
                    if result.stderr:
                        console.print(f"[red]{result.stderr}[/red]", end="")

                    # Show exit code if non-zero
                    if result.returncode != 0:
                        console.print(f"[dim]Exit code: {result.returncode}[/dim]")
                except Exception as e:
                    console.print_error(f"Error executing command: {e}")
                continue

            # Handle ! prefix for bash commands (inline bash mode in CHAT mode)
            if user_input.startswith("!"):
                # Remove the ! prefix and execute as bash command
                bash_command = user_input[1:].strip()

                if not bash_command:
                    console.print("[yellow]Usage: ! <command>[/yellow]")
                    console.print("[dim]Example: ! ls -la[/dim]")
                    console.print("[dim]Or press Shift+Tab to enter bash mode[/dim]")
                    continue

                try:
                    # Execute bash command and capture output
                    result = subprocess.run(
                        bash_command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        check=False  # Don't raise exception on non-zero exit codes
                    )

                    # Show output
                    if result.stdout:
                        console.print(result.stdout, end="")
                    if result.stderr:
                        console.print(f"[red]{result.stderr}[/red]", end="")

                    # Show exit code if non-zero
                    if result.returncode != 0:
                        console.print(f"[dim]Exit code: {result.returncode}[/dim]")
                except Exception as e:
                    console.print_error(f"Error executing command: {e}")
                continue

            # Regular chat with AI agent
            try:
                chat_turn(
                    conversation=conversation,
                    user_input=user_input,
                    tools=tools,
                    tool_executor=tool_executor,
                    console=rich_console,
                    hook_config=hook_config,
                )
            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted[/dim]")
                continue
            except Exception as e:
                console.print_error(f"Error: {e}")
                continue

            console.print()  # Blank line after response

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break


@main.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key: str | None, value: str | None) -> None:
    """View or modify configuration.

    Without arguments, shows the config file path.
    With KEY, shows that config value.
    With KEY and VALUE, sets the config value.
    """
    cfg = load_config()

    if key is None:
        # Show config path and summary
        click.echo(f"Config file: {get_config_path()}")
        click.echo(f"Default model: {cfg.default_model}")
        click.echo(f"Model aliases: {len(cfg.models)}")
        return

    if value is None:
        # Show specific key
        if key == "default_model":
            click.echo(cfg.default_model)
        elif key == "models":
            for alias, model in cfg.models.items():
                click.echo(f"  {alias}: {model}")
        else:
            click.echo(f"Unknown config key: {key}", err=True)
        return

    # Set value
    if key == "default_model":
        cfg.default_model = value
        save_config(cfg)
        click.echo(f"Set default_model to: {value}")
    else:
        click.echo(f"Cannot set config key: {key}", err=True)


@main.command()
def mcp_server() -> None:
    """Run loco as an MCP server (exposes tools via stdio).
    
    This allows other MCP clients (like Claude Desktop) to use loco's tools.
    
    Example configuration for Claude Desktop (~/.config/claude/claude_desktop_config.json):
    
    \b
    {
      "mcpServers": {
        "loco": {
          "command": "loco",
          "args": ["mcp-server"]
        }
      }
    }
    """
    import asyncio
    from loco.mcp.server import MCPServer
    from loco.tools import (
        ReadTool, WriteTool, EditTool, BashTool, GlobTool, GrepTool
    )
    
    # Register all loco tools
    server = MCPServer(name="loco", version=__version__)
    server.register_tool(ReadTool())
    server.register_tool(WriteTool())
    server.register_tool(EditTool())
    server.register_tool(BashTool())
    server.register_tool(GlobTool())
    server.register_tool(GrepTool())
    
    # Run the server
    asyncio.run(server.run())


@main.group()
def mcp() -> None:
    """Manage MCP servers."""
    pass



@mcp.command()
@click.argument("name")
@click.argument("json_config")
def add_json(name: str, json_config: str) -> None:
    """Add an MCP server from JSON configuration.

    Supports both command-based and HTTP-based MCP servers.
    
    Command-based example:
      loco mcp add-json filesystem '{"type":"command","command":["npx","-y","@modelcontextprotocol/server-filesystem","/path"]}'
    
    HTTP-based example:
      loco mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer TOKEN"}}'
    """
    import json
    from loco.config import load_config, save_config, MCPServerConfig

    try:
        config_data = json.loads(json_config)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")

    # Validate config using Pydantic model
    try:
        server_config = MCPServerConfig(**config_data)
    except Exception as e:
        raise click.ClickException(f"Invalid MCP server configuration: {e}")

    # Load current config
    config = load_config()

    # Add new MCP server (store as dict)
    config.mcp_servers[name] = server_config.model_dump(exclude_none=True)

    # Save updated config
    save_config(config)

    config_type = server_config.type
    click.echo(f"Added {config_type}-based MCP server '{name}' to configuration")


if __name__ == "__main__":
    main()


@mcp.command(name="list")
def list_servers() -> None:
    """List all configured MCP servers."""
    from loco.config import load_config
    from rich.table import Table
    
    console = get_console()
    config = load_config()
    
    if not config.mcp_servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        console.print("\nAdd one with: [cyan]loco mcp add-json <name> '<json-config>'[/cyan]")
        return
    
    table = Table(title="Configured MCP Servers", show_header=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Details", style="white")
    
    for name, server_config in config.mcp_servers.items():
        if isinstance(server_config, dict):
            config_type = server_config.get('type', 'command')
            
            if config_type == 'http':
                url = server_config.get('url', 'N/A')
                headers_count = len(server_config.get('headers', {}))
                details = f"{url} ({headers_count} header(s))"
            else:
                cmd = server_config.get('command', ['N/A'])
                cmd_str = ' '.join(cmd[:2]) if isinstance(cmd, list) else str(cmd)
                args = server_config.get('args', [])
                if args:
                    cmd_str += f" +{len(args)} arg(s)"
                details = cmd_str
        else:
            config_type = server_config.type
            details = "Unknown"
        
        table.add_row(name, config_type.upper(), details)
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(config.mcp_servers)} server(s)[/dim]")


@mcp.command()
@click.argument("name")
def remove(name: str) -> None:
    """Remove an MCP server from configuration."""
    from loco.config import load_config, save_config
    
    console = get_console()
    config = load_config()
    
    if name not in config.mcp_servers:
        raise click.ClickException(f"MCP server '{name}' not found")
    
    # Get server type for confirmation message
    server_config = config.mcp_servers[name]
    if isinstance(server_config, dict):
        config_type = server_config.get('type', 'command')
    else:
        config_type = server_config.type
    
    # Remove the server
    del config.mcp_servers[name]
    save_config(config)
    
    console.print(f"[green]✓[/green] Removed {config_type}-based MCP server '{name}'")


@mcp.command()
@click.argument("name")
def show(name: str) -> None:
    """Show detailed configuration for an MCP server."""
    import json
    from loco.config import load_config
    
    console = get_console()
    config = load_config()
    
    if name not in config.mcp_servers:
        raise click.ClickException(f"MCP server '{name}' not found")
    
    server_config = config.mcp_servers[name]
    
    # Convert to dict if needed
    if not isinstance(server_config, dict):
        config_dict = server_config.model_dump(exclude_none=True)
    else:
        config_dict = server_config.copy()
    
    # Mask sensitive data in headers
    if 'headers' in config_dict and config_dict['headers']:
        masked_headers = {}
        for key, value in config_dict['headers'].items():
            if any(sensitive in key.lower() for sensitive in ['auth', 'token', 'key', 'secret', 'password']):
                masked_headers[key] = value[:10] + '...' if len(value) > 10 else '***'
            else:
                masked_headers[key] = value
        config_dict['headers'] = masked_headers
    
    console.print(f"\n[bold cyan]MCP Server: {name}[/bold cyan]")
    console.print(json.dumps(config_dict, indent=2))


@mcp.command()
@click.argument("name", required=False)
@click.option("--timeout", default=10, help="Timeout in seconds for initialization")
def test(name: str | None, timeout: int) -> None:
    """Test connectivity and initialization of MCP server(s).
    
    If no name is provided, tests all configured servers.
    """
    import asyncio
    from loco.config import load_config
    from loco.mcp.loader import load_mcp_client
    
    console = get_console()
    config = load_config()
    
    if not config.mcp_servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        return
    
    # Determine which servers to test
    if name:
        if name not in config.mcp_servers:
            raise click.ClickException(f"MCP server '{name}' not found")
        servers_to_test = {name: config.mcp_servers[name]}
    else:
        servers_to_test = config.mcp_servers
    
    async def test_server(server_name: str) -> tuple[str, bool, str]:
        """Test a single server. Returns (name, success, message)."""
        try:
            client = load_mcp_client(config, server_name)
            if client is None:
                return (server_name, False, "Failed to create client")
            
            # Try to initialize
            result = await asyncio.wait_for(
                client.initialize(),
                timeout=timeout
            )
            
            # Try to list tools
            tools = await asyncio.wait_for(
                client.list_tools(),
                timeout=timeout
            )
            
            await client.close()
            
            return (server_name, True, f"OK - {len(tools)} tool(s) available")
        except asyncio.TimeoutError:
            return (server_name, False, f"Timeout after {timeout}s")
        except Exception as e:
            return (server_name, False, str(e))
    
    async def test_all():
        tasks = [test_server(name) for name in servers_to_test.keys()]
        return await asyncio.gather(*tasks)
    
    console.print(f"[dim]Testing {len(servers_to_test)} server(s)...[/dim]\n")
    
    results = asyncio.run(test_all())
    
    for server_name, success, message in results:
        if success:
            console.print(f"[green]✓[/green] {server_name}: {message}")
        else:
            console.print(f"[red]✗[/red] {server_name}: {message}")


@mcp.command()
@click.argument("name", required=False)
@click.option("--timeout", default=10, help="Timeout in seconds")
def tools(name: str | None, timeout: int) -> None:
    """List available tools from MCP server(s).
    
    If no name is provided, lists tools from all configured servers.
    """
    import asyncio
    from loco.config import load_config
    from loco.mcp.loader import load_mcp_client
    from rich.table import Table
    
    console = get_console()
    config = load_config()
    
    if not config.mcp_servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        return
    
    # Determine which servers to query
    if name:
        if name not in config.mcp_servers:
            raise click.ClickException(f"MCP server '{name}' not found")
        servers_to_query = {name: config.mcp_servers[name]}
    else:
        servers_to_query = config.mcp_servers
    
    async def get_tools(server_name: str):
        """Get tools from a single server."""
        try:
            client = load_mcp_client(config, server_name)
            if client is None:
                return (server_name, None, "Failed to create client")
            
            await asyncio.wait_for(client.initialize(), timeout=timeout)
            tools = await asyncio.wait_for(client.list_tools(), timeout=timeout)
            await client.close()
            
            return (server_name, tools, None)
        except asyncio.TimeoutError:
            return (server_name, None, f"Timeout after {timeout}s")
        except Exception as e:
            return (server_name, None, str(e))
    
    async def get_all_tools():
        tasks = [get_tools(name) for name in servers_to_query.keys()]
        return await asyncio.gather(*tasks)
    
    console.print(f"[dim]Querying {len(servers_to_query)} server(s)...[/dim]\n")
    
    results = asyncio.run(get_all_tools())
    
    # Display results
    for server_name, tools, error in results:
        if error:
            console.print(f"[red]✗[/red] {server_name}: {error}")
            continue
        
        if not tools:
            console.print(f"[yellow]⚠[/yellow] {server_name}: No tools available")
            continue
        
        table = Table(title=f"Tools from '{server_name}'", show_header=True)
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        
        for tool in tools:
            description = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
            table.add_row(tool.name, description)
        
        console.print(table)
        console.print()


