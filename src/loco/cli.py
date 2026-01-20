"""CLI entry point for loco."""

import os
import sys
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
from loco.skills import skill_registry, get_skills_system_prompt_section, Skill
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


# Track current session ID for auto-save
_current_session_id: str | None = None

# Track active skill for current conversation
_active_skill: Skill | None = None


def handle_slash_command(
    command: str,
    conversation: Conversation,
    config: Config,
    console: Console,
) -> bool:
    """Handle slash commands. Returns True if command was handled."""
    global _current_session_id, _active_skill

    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        console.print("""
[bold]Available Commands:[/bold]

  [cyan]/help[/cyan]             Show this help message
  [cyan]/clear[/cyan]            Clear conversation history
  [cyan]/model[/cyan] [name]     Show or switch the current model
  [cyan]/skill[/cyan] [name]     Activate a skill or list available skills
  [cyan]/skills[/cyan]           List all available skills
  [cyan]/agent[/cyan] <name> <task>  Run a subagent with a task
  [cyan]/agents[/cyan]           List all available agents
  [cyan]/save[/cyan] [name]      Save current conversation
  [cyan]/load[/cyan] <id>        Load a saved conversation
  [cyan]/sessions[/cyan]         List saved sessions
  [cyan]/stats[/cyan]            Show token usage and cost statistics
  [cyan]/context[/cyan]          Show context window usage and estimates
  [cyan]/plan[/cyan] <task>      Create a step-by-step plan for a task
  [cyan]/commit[/cyan]           Generate and create a smart commit message
  [cyan]/pr[/cyan]               Generate a pull request description
  [cyan]/config[/cyan]           Show configuration file path
  [cyan]/quit[/cyan]             Exit loco (or Ctrl+C)

[bold]Tips:[/bold]
- Use model aliases from config (e.g., /model gpt4)
- Or use full LiteLLM model strings (e.g., /model openai/gpt-4o)
- Skills are loaded from .loco/skills/, .claude/skills/, and ~/.config/loco/skills/
- Agents are loaded from .loco/agents/, .claude/agents/, and ~/.config/loco/agents/
""")
        return True

    elif cmd == "/clear":
        conversation.clear()
        conversation.usage = None
        _current_session_id = None
        _active_skill = None
        console.print("[dim]Conversation cleared.[/dim]")
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
            approval = console.get_input("> ")
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
                        continue_resp = console.get_input("> ")
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

    elif cmd == "/commit":
        git_status = get_git_status()

        if not git_status.is_repo:
            console.print("[red]Not in a git repository[/red]")
            return True

        if not git_status.has_changes():
            console.print("[dim]No changes to commit[/dim]")
            return True

        # Show current status
        console.print(f"[bold]Current branch:[/bold] {git_status.branch}")
        if git_status.staged_files:
            console.print(f"[green]Staged files:[/green] {len(git_status.staged_files)}")
        if git_status.unstaged_files:
            console.print(f"[yellow]Unstaged files:[/yellow] {len(git_status.unstaged_files)}")

        # Ask if we should stage all changes
        if git_status.unstaged_files:
            console.print("\n[yellow]Stage all changes?[/yellow] [dim](yes/no)[/dim]")
            stage_response = console.get_input("> ")
            if stage_response and stage_response.lower() in ["yes", "y"]:
                stage_all_changes()
                console.print("[dim]Staged all changes[/dim]")

        # Get diff
        diff = get_staged_diff() or get_all_diff()
        if not diff:
            console.print("[red]No diff found[/red]")
            return True

        # Generate commit message
        console.print("\n[dim]Generating commit message...[/dim]")
        prompt = generate_commit_message_prompt(diff)

        # Create temporary conversation for commit message
        commit_conv = Conversation(model=conversation.model, config=conversation.config)
        commit_conv.add_user_message(prompt)

        try:
            commit_message = ""
            with console.console.status("[dim]Thinking...[/dim]"):
                from loco.chat import stream_response
                for item in stream_response(commit_conv, tools=None):
                    if isinstance(item, str):
                        commit_message += item

            commit_message = commit_message.strip()

            # Show generated message
            console.print("\n[bold]Generated commit message:[/bold]")
            console.print(f"[cyan]{commit_message}[/cyan]")
            console.print("\n[bold]Create this commit?[/bold] [dim](yes/no/edit)[/dim]")

            response = console.get_input("> ")

            if response and response.lower() == "edit":
                console.print("\n[dim]Enter your commit message (press Ctrl+D when done):[/dim]")
                edited_message = console.get_multiline_input("> ")
                if edited_message:
                    commit_message = edited_message.strip()
                else:
                    console.print("[dim]Commit cancelled[/dim]")
                    return True
            elif not response or response.lower() not in ["yes", "y"]:
                console.print("[dim]Commit cancelled[/dim]")
                return True

            # Create commit
            success, output = create_commit(commit_message)
            if success:
                console.print(f"[green]✓[/green] Commit created successfully")
                console.print(f"[dim]{output}[/dim]")
            else:
                console.print(f"[red]Failed to create commit:[/red]")
                console.print(output)

        except Exception as e:
            console.print(f"[red]Error generating commit message: {e}[/red]")

        return True

    elif cmd == "/pr":
        git_status = get_git_status()

        if not git_status.is_repo:
            console.print("[red]Not in a git repository[/red]")
            return True

        branch = git_status.branch
        if not branch:
            console.print("[red]Not on a branch[/red]")
            return True

        if branch in ["main", "master"]:
            console.print("[yellow]Warning: You're on the main/master branch[/yellow]")
            console.print("[dim]Usually you'd create a PR from a feature branch[/dim]")

        # Get base branch (default to main)
        console.print("[bold]Base branch?[/bold] [dim](default: main)[/dim]")
        base_branch = console.get_input("> ") or "main"

        console.print(f"\n[dim]Generating PR description for {branch} → {base_branch}...[/dim]")

        # Get commit history and diff
        commits = get_commit_history(base_branch)
        diff = get_branch_diff(base_branch)

        if not commits and not diff:
            console.print("[red]No changes found between branches[/red]")
            return True

        # Generate PR description
        prompt = generate_pr_description_prompt(branch, base_branch, commits, diff or "")

        pr_conv = Conversation(model=conversation.model, config=conversation.config)
        pr_conv.add_user_message(prompt)

        try:
            pr_description = ""
            with console.console.status("[dim]Thinking...[/dim]"):
                from loco.chat import stream_response
                for item in stream_response(pr_conv, tools=None):
                    if isinstance(item, str):
                        pr_description += item

            # Display PR description
            console.print("\n[bold]Generated PR Description:[/bold]\n")
            console.print_markdown(pr_description)

            # Save to file
            pr_file = Path(".loco") / "PR_DESCRIPTION.md"
            pr_file.parent.mkdir(exist_ok=True)
            pr_file.write_text(pr_description)

            console.print(f"\n[green]✓[/green] PR description saved to: [cyan]{pr_file}[/cyan]")
            console.print("[dim]You can use this when creating your pull request[/dim]")

        except Exception as e:
            console.print(f"[red]Error generating PR description: {e}[/red]")

        return True

    elif cmd in ("/skill", "/skills"):
        skills = skill_registry.get_user_invocable()

        if not args or cmd == "/skills":
            # List available skills
            if not skills:
                console.print("[dim]No skills found.[/dim]")
                console.print("[dim]Add skills to .loco/skills/, .claude/skills/, or ~/.config/loco/skills/[/dim]")
                return True

            console.print("[bold]Available Skills:[/bold]\n")
            for skill in skills:
                active_marker = " [green]<-- active[/green]" if _active_skill and _active_skill.name == skill.name else ""
                console.print(f"  [cyan]{skill.name}[/cyan]: {skill.description}{active_marker}")

            if _active_skill:
                console.print(f"\n[dim]Active skill: {_active_skill.name}[/dim]")
                console.print("[dim]Use /skill off to deactivate[/dim]")
            return True

        # Activate or deactivate a skill
        if args.lower() == "off":
            if _active_skill:
                console.print(f"[dim]Deactivated skill: {_active_skill.name}[/dim]")
                _active_skill = None
                # Rebuild system prompt without skill
                conversation.add_system_message(
                    get_default_system_prompt(os.getcwd(), get_skills_system_prompt_section())
                )
            else:
                console.print("[dim]No active skill to deactivate[/dim]")
            return True

        # Find and activate the skill
        skill = skill_registry.get(args)
        if skill is None:
            console.print(f"[red]Skill not found: {args}[/red]")
            console.print("[dim]Use /skills to see available skills[/dim]")
            return True

        _active_skill = skill
        # Update system prompt with skill content
        skills_section = get_skills_system_prompt_section()
        skills_section += skill.get_system_prompt_addition()
        conversation.add_system_message(
            get_default_system_prompt(os.getcwd(), skills_section)
        )
        console.print(f"[dim]Activated skill: {skill.name}[/dim]")
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

    elif cmd == "/config":
        console.print(f"[dim]Config file: {get_config_path()}[/dim]")
        return True

    elif cmd in ("/quit", "/exit", "/q"):
        console.print("[dim]Goodbye![/dim]")
        sys.exit(0)

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
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context, model: str | None, cwd: str | None) -> None:
    """Loco - LLM Coding Assistant CLI.

    An AI-powered coding assistant that works with any OpenAI-compatible LLM.
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

    # Change working directory if specified
    if cwd:
        os.chdir(cwd)

    # Resolve model
    effective_model = resolve_model(model or config.default_model, config)

    # Discover skills and agents
    skill_registry.discover()
    agent_registry.discover()
    skills_section = get_skills_system_prompt_section()

    # Initialize UI
    console = get_console()
    rich_console = console.console

    # Print welcome
    console.print_welcome(effective_model, os.getcwd())

    # Show discovered skills and agents count
    skill_count = len(skill_registry.get_all())
    agent_count = len(agent_registry.get_all())
    info_parts = []
    if skill_count > 0:
        info_parts.append(f"{skill_count} skill(s)")
    if agent_count > 0:
        info_parts.append(f"{agent_count} agent(s)")
    if info_parts:
        console.print(f"[dim]{', '.join(info_parts)} available.[/dim]\n")

    # Initialize conversation
    conversation = Conversation(
        model=effective_model,
        config=config,
    )
    conversation.add_system_message(get_default_system_prompt(os.getcwd(), skills_section))

    # Get tools
    tools = tool_registry.get_openai_tools()

    # Initialize hooks
    hook_config = HookConfig.from_dict(config.hooks) if config.hooks else None

    # Main loop
    while True:
        try:
            user_input = console.get_input("> ")

            if user_input is None:
                # Ctrl+C or Ctrl+D
                console.print("\n[dim]Goodbye![/dim]")
                break

            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                if handle_slash_command(user_input, conversation, config, console):
                    continue
                else:
                    console.print_error(f"Unknown command: {user_input.split()[0]}")
                    console.print("[dim]Type /help for available commands[/dim]")
                    continue

            # Regular chat
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


if __name__ == "__main__":
    main()
