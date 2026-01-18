"""CLI entry point for loco."""

import os
import sys
from pathlib import Path

import click
from rich.console import Console

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
from loco.ui.console import get_console
from loco.history import save_conversation, load_conversation, list_sessions
from loco.skills import skill_registry, get_skills_system_prompt_section, Skill
from loco.hooks import HookConfig
from loco.agents import agent_registry, run_agent


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
  [cyan]/config[/cyan]           Show configuration file path
  [cyan]/quit[/cyan]             Exit loco (or Ctrl+C)

[bold]Tips:[/bold]
- Use model aliases from config (e.g., /model gpt4)
- Or use full LiteLLM model strings (e.g., /model openai/gpt-4o)
- Skills are loaded from .loco/skills/ and ~/.config/loco/skills/
- Agents are loaded from .loco/agents/ and ~/.config/loco/agents/
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

    elif cmd in ("/skill", "/skills"):
        skills = skill_registry.get_user_invocable()

        if not args or cmd == "/skills":
            # List available skills
            if not skills:
                console.print("[dim]No skills found.[/dim]")
                console.print("[dim]Add skills to .loco/skills/ or ~/.config/loco/skills/[/dim]")
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
                console.print("[dim]Add agents to .loco/agents/ or ~/.config/loco/agents/[/dim]")
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
                if handle_slash_command(user_input, conversation, config, rich_console):
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


if __name__ == "__main__":
    main()
