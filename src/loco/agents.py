"""Subagents system for loco - isolated AI assistants for complex tasks."""

import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from loco.config import Config, get_config_dir
from loco.telemetry import track_agent, OperationType, track_operation


@dataclass
class Agent:
    """A subagent definition loaded from an agent markdown file."""

    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    model: str | None = None
    path: Path | None = None

    def get_effective_tools(self, all_tools: list[str]) -> list[str]:
        """Get the list of tools this agent can use.

        If allowed_tools is set, only those tools are available.
        If disallowed_tools is set, those are removed from all tools.
        """
        if self.allowed_tools is not None:
            return [t for t in self.allowed_tools if t in all_tools]

        if self.disallowed_tools is not None:
            return [t for t in all_tools if t not in self.disallowed_tools]

        return all_tools


@dataclass
class AgentRegistry:
    """Registry for discovering and managing agents."""

    agents: dict[str, Agent] = field(default_factory=dict)
    _discovered: bool = False

    def discover(self, project_dir: Path | None = None) -> None:
        """Discover agents from all locations.

        Locations (in precedence order, later overrides earlier):
        1. User agents: ~/.config/loco/agents/
        2. Claude Desktop agents: .claude/agents/ (for compatibility)
        3. Project agents: .loco/agents/ (highest priority)

        Note: .claude/ support enables seamless integration with Claude Desktop
        configurations. Both .claude/ and .loco/ can coexist in the same project.
        """
        self.agents.clear()

        # User agents (lowest precedence)
        user_agents_dir = get_config_dir() / "agents"
        self._load_agents_from_dir(user_agents_dir)

        # Project directory to search
        search_dir = project_dir if project_dir else Path.cwd()

        # Claude Desktop agents (middle precedence)
        claude_agents_dir = search_dir / ".claude" / "agents"
        self._load_agents_from_dir(claude_agents_dir)

        # Loco project agents (highest precedence)
        loco_agents_dir = search_dir / ".loco" / "agents"
        self._load_agents_from_dir(loco_agents_dir)

        self._discovered = True

    def _load_agents_from_dir(self, agents_dir: Path) -> None:
        """Load all agents from a directory."""
        if not agents_dir.exists():
            return

        # Agents are markdown files: agents/agent-name.md
        for agent_file in agents_dir.glob("*.md"):
            try:
                agent = self._parse_agent_file(agent_file)
                if agent:
                    self.agents[agent.name] = agent
            except Exception as e:
                print(f"Warning: Failed to load agent from {agent_file}: {e}")

    def _parse_agent_file(self, path: Path) -> Agent | None:
        """Parse an agent markdown file into an Agent object."""
        content = path.read_text()

        # Parse YAML frontmatter
        frontmatter: dict[str, Any] = {}
        body = content

        if content.startswith("---"):
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if match:
                try:
                    frontmatter = yaml.safe_load(match.group(1)) or {}
                except yaml.YAMLError:
                    frontmatter = {}
                body = match.group(2)

        # Extract fields
        name = frontmatter.get("name", path.stem)
        description = frontmatter.get("description", "")

        if not description:
            # Try to extract from first paragraph
            lines = body.strip().split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break

        # Parse allowed/disallowed tools
        allowed_tools = frontmatter.get("tools") or frontmatter.get("allowed-tools")
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",")]

        disallowed_tools = frontmatter.get("disallowed-tools")
        if isinstance(disallowed_tools, str):
            disallowed_tools = [t.strip() for t in disallowed_tools.split(",")]

        return Agent(
            name=name,
            description=description,
            system_prompt=body.strip(),
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            model=frontmatter.get("model"),
            path=path,
        )

    def get(self, name: str) -> Agent | None:
        """Get an agent by name."""
        if not self._discovered:
            self.discover()
        return self.agents.get(name)

    def get_all(self) -> list[Agent]:
        """Get all discovered agents."""
        if not self._discovered:
            self.discover()
        return list(self.agents.values())

    def match_agent(self, task_description: str) -> Agent | None:
        """Find an agent that matches the task description.

        Uses simple keyword matching. For better results,
        you could use embeddings or LLM-based matching.
        """
        if not self._discovered:
            self.discover()

        task_lower = task_description.lower()
        best_match: tuple[int, Agent | None] = (0, None)

        for agent in self.agents.values():
            score = 0
            desc_lower = agent.description.lower()
            name_lower = agent.name.lower()

            # Check if agent name is mentioned
            if name_lower in task_lower:
                score += 10

            # Check keyword overlap
            desc_words = set(desc_lower.split())
            task_words = set(task_lower.split())
            overlap = desc_words & task_words
            score += len(overlap) * 2

            if score > best_match[0]:
                best_match = (score, agent)

        # Only return if score is meaningful
        if best_match[0] >= 3:
            return best_match[1]

        return None


@dataclass
class AgentRun:
    """Represents a running or completed agent execution."""

    id: str
    agent: Agent
    task: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    result: str | None = None
    completed: bool = False

    @classmethod
    def create(cls, agent: Agent, task: str) -> "AgentRun":
        """Create a new agent run."""
        return cls(
            id=str(uuid.uuid4())[:8],
            agent=agent,
            task=task,
        )


# Global registry instance
agent_registry = AgentRegistry()


def run_agent(
    agent: Agent,
    task: str,
    config: Config,
    tool_registry: Any,
    console: Any,
) -> str:
    """Run an agent with an isolated conversation context.

    Args:
        agent: The agent to run
        task: The task description
        config: Main config for provider settings
        tool_registry: Registry of available tools
        console: Rich console for output

    Returns:
        The agent's final response
    """
    from loco.chat import Conversation, chat_turn, ToolCall
    from loco.hooks import HookConfig

    # Determine model
    model = agent.model or config.default_model
    if "/" not in model:
        # Resolve alias
        from loco.config import resolve_model
        model = resolve_model(model, config)

    # Create isolated conversation
    conversation = Conversation(
        model=model,
        config=config,
    )

    # Build system prompt with agent instructions
    system_prompt = f"""You are a specialized agent: {agent.name}

{agent.system_prompt}

Current task: {task}

Complete this task and provide a clear summary of what you found or accomplished."""

    conversation.add_system_message(system_prompt)

    # Get filtered tools
    all_tool_names = [t.name for t in tool_registry.get_all()]
    allowed_tools = agent.get_effective_tools(all_tool_names)

    # Filter tool definitions
    all_tools = tool_registry.get_openai_tools()
    filtered_tools = [
        t for t in all_tools
        if t["function"]["name"] in allowed_tools
    ]

    # Create tool executor
    def tool_executor(tc: ToolCall) -> str:
        if tc.name not in allowed_tools:
            return f"Error: Tool '{tc.name}' is not available to this agent"
        return tool_registry.execute(tc.name, tc.arguments)

    # Initialize hooks if configured
    hook_config = HookConfig.from_dict(config.hooks) if config.hooks else None

    # Show agent header
    console.print(f"\n[bold cyan]Agent: {agent.name}[/bold cyan]")
    console.print(f"[dim]Task: {task}[/dim]\n")

    # Determine operation type based on agent name
    op_type = OperationType.UNKNOWN
    if "explore" in agent.name.lower():
        op_type = OperationType.AGENT_EXPLORATION
    elif "research" in agent.name.lower():
        op_type = OperationType.AGENT_RESEARCH
    elif "rails" in agent.name.lower():
        op_type = OperationType.AGENT_RAILS
    else:
        op_type = OperationType.AGENT_OVERHEAD

    # Run the conversation
    with track_agent(agent.name):
        with track_operation(op_type):
            try:
                chat_turn(
                    conversation=conversation,
                    user_input=task,
                    tools=filtered_tools if filtered_tools else None,
                    tool_executor=tool_executor,
                    console=console,
                    hook_config=hook_config,
                )
            except Exception as e:
                return f"Agent error: {e}"

    # Get the final response
    for msg in reversed(conversation.messages):
        if msg.role == "assistant" and msg.content:
            return msg.content

    return "Agent completed without a response"
