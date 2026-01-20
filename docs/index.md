---
layout: default
---

# 🚂 loco

**Your AI coding assistant, any LLM, anywhere.**

A Claude Code-inspired CLI that works with OpenAI, Bedrock, Ollama, and 100+ LLM providers via LiteLLM.

---

## Quick Start

```bash
pip install git+https://github.com/showdownlabs/loco.git
loco
```

That's it. Loco creates a config file on first run.

---

## Why loco?

- **Use any LLM** — Not locked into one provider. Switch between OpenAI, Bedrock, Ollama, or your own LiteLLM proxy.
- **Claude Code UX** — Familiar interface with streaming, tools, and markdown rendering.
- **Extensible** — Add skills for common tasks, hooks for automation, agents for specialized work.
- **Secure** — No external server. Direct API calls only. Your code stays local.

---

## Installation

### From Git

```bash
pip install git+https://github.com/showdownlabs/loco.git
```

### For Development

```bash
git clone https://github.com/showdownlabs/loco.git
cd loco
pip install -e .
```

### With pipx (Recommended)

```bash
pipx install git+https://github.com/showdownlabs/loco.git
```

---

## Configuration

Config lives at `~/.config/loco/config.json`. Created automatically on first run.

```json
{
  "default_model": "openai/gpt-4o",
  "models": {
    "gpt4": "openai/gpt-4o",
    "sonnet": "bedrock/us.anthropic.claude-sonnet-4-20250514",
    "local": "ollama/llama3"
  },
  "providers": {
    "openai": {
      "api_key": "${OPENAI_API_KEY}"
    },
    "bedrock": {
      "aws_region": "us-west-2"
    }
  }
}
```

### Environment Variables

Use `${VAR}` syntax to reference environment variables:

```json
{
  "providers": {
    "openai": { "api_key": "${OPENAI_API_KEY}" }
  }
}
```

### Model Aliases

Define shortcuts for frequently used models:

```json
{
  "models": {
    "fast": "openai/gpt-4o-mini",
    "smart": "openai/gpt-4o",
    "local": "ollama/llama3"
  }
}
```

Then use them: `loco -m fast`

---

## Usage

```bash
loco                    # Start with default model
loco -m gpt4            # Use a model alias
loco -m openai/gpt-4o   # Use full model name
loco -C ~/projects/app  # Start in specific directory
```

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model [name]` | Switch or show current model |
| `/skill [name]` | Activate a skill |
| `/skills` | List available skills |
| `/agent <name> <task>` | Run a subagent |
| `/agents` | List available agents |
| `/save [name]` | Save conversation |
| `/load <id>` | Load conversation |
| `/sessions` | List saved sessions |
| `/clear` | Clear conversation history |
| `/config` | Show config file path |
| `/quit` | Exit (or Ctrl+C) |

---

## Built-in Tools

Loco includes 6 tools that the LLM can use:

| Tool | Description |
|------|-------------|
| **read** | Read file contents with line numbers |
| **write** | Create or overwrite files |
| **edit** | Edit files via string replacement |
| **bash** | Execute shell commands |
| **glob** | Find files by pattern (e.g., `**/*.py`) |
| **grep** | Search file contents with regex |

---

## Skills

Skills are reusable prompts that teach the LLM specific tasks.

### Location

- **Project:** `.loco/skills/skill-name/SKILL.md`
- **Claude Desktop:** `.claude/skills/skill-name/SKILL.md` (compatible)
- **User:** `~/.config/loco/skills/skill-name/SKILL.md`

> **Note:** `.claude/` directories enable seamless integration with Claude Desktop. Use `.loco/` for project-specific overrides.

### Creating a Skill

Create a markdown file with YAML frontmatter:

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
allowed-tools: read, grep, glob
user-invocable: true
---

# Code Reviewer

You are a code review expert. When asked to review code:

1. Check for bugs and logic errors
2. Evaluate code style and readability
3. Look for security vulnerabilities
4. Suggest improvements

Be specific and constructive in your feedback.
```

### Using Skills

```
/skills            # List available skills
/skill reviewer    # Activate a skill
/skill off         # Deactivate current skill
```

### Example Skills

Copy from `examples/skills/` to get started:

- **code-reviewer** — Reviews code for quality issues
- **test-writer** — Generates comprehensive tests
- **debugger** — Helps debug issues systematically

---

## Hooks

Hooks are shell commands that run at lifecycle events. Use them to validate, modify, or block tool calls.

### Events

| Event | When | Can |
|-------|------|-----|
| `PreToolUse` | Before tool executes | Approve, deny, or modify |
| `PostToolUse` | After tool executes | Add context to response |

### Configuration

Add to `~/.config/loco/config.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "bash",
        "hooks": [
          { "type": "command", "command": "/path/to/validate.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "write|edit",
        "hooks": [
          { "type": "command", "command": "/path/to/format.sh" }
        ]
      }
    ]
  }
}
```

### Hook Protocol

Hooks receive JSON on stdin:

```json
{
  "hook_event": "PreToolUse",
  "tool_name": "bash",
  "tool_input": { "command": "ls -la" },
  "cwd": "/current/dir"
}
```

Hooks output JSON on stdout:

```json
{
  "decision": "deny",
  "reason": "Blocked dangerous command"
}
```

Exit codes:
- `0` — Success
- `2` — Blocking error
- Other — Non-blocking error

### Example Hooks

Copy from `examples/hooks/`:

- **block-dangerous-commands.sh** — Blocks `rm -rf /`, fork bombs, etc.
- **format-on-write.sh** — Auto-formats with black/prettier/gofmt
- **lint-on-write.sh** — Runs linters after file changes

---

## Agents

Agents are subagents with isolated contexts and restricted tools. Use them for focused tasks.

### Location

- **Project:** `.loco/agents/agent-name.md`
- **Claude Desktop:** `.claude/agents/agent-name.md` (compatible)
- **User:** `~/.config/loco/agents/agent-name.md`

> **Note:** `.claude/` directories enable seamless integration with Claude Desktop. Use `.loco/` for project-specific overrides.

### Creating an Agent

```markdown
---
name: explorer
description: Fast codebase exploration
tools: read, glob, grep
model: haiku
---

# Explorer Agent

You are a fast codebase exploration agent. Your job is to quickly
find information in the codebase.

## Guidelines

1. Use glob to find relevant files
2. Use grep to search contents
3. Read specific files only when needed
4. Summarize findings clearly
```

### Options

| Option | Description |
|--------|-------------|
| `name` | Agent identifier |
| `description` | When to use this agent |
| `tools` | Allowed tools (allowlist) |
| `disallowed-tools` | Blocked tools (denylist) |
| `model` | Model override (alias or full name) |

### Using Agents

```
/agents                          # List available agents
/agent explorer find API routes  # Run agent with task
```

### Example Agents

Copy from `examples/agents/`:

- **explorer** — Fast codebase exploration (read-only)
- **planner** — Implementation planning (no write access)
- **refactor** — Safe code refactoring

---

## Supported Providers

Via [LiteLLM](https://docs.litellm.ai/docs/providers), loco supports 100+ providers:

| Provider | Model Format |
|----------|--------------|
| OpenAI | `openai/gpt-4o` |
| Amazon Bedrock | `bedrock/us.anthropic.claude-sonnet-4-20250514` |
| OpenRouter | `openrouter/anthropic/claude-3.5-sonnet` |
| Ollama | `ollama/llama3` |
| LM Studio | `lm_studio/local-model` |
| Azure OpenAI | `azure/deployment-name` |
| Together AI | `together_ai/model-name` |
| Anyscale | `anyscale/model-name` |
| Replicate | `replicate/model-name` |

See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for the full list.

### Using a LiteLLM Proxy

If you run a LiteLLM proxy server:

```json
{
  "default_model": "my-model",
  "providers": {
    "litellm_proxy": {
      "api_base": "https://your-proxy.com/v1",
      "api_key": "${LITELLM_API_KEY}"
    }
  }
}
```

---

## Documentation

### 📘 Guides

- **[Quick Start Guide](QUICKSTART.md)** — Hands-on examples and workflows to get started quickly
- **[Architecture & Flow](ARCHITECTURE.md)** — Detailed diagrams showing how loco processes requests
- **[Technical Analysis](ANALYSIS.md)** — Deep dive into loco's design, patterns, and implementation

### 🔗 MCP (Model Context Protocol)

- **[MCP Guide](MCP.md)** — Comprehensive guide to MCP server and client functionality
- **[MCP Quick Reference](MCP_QUICK_REFERENCE.md)** — Quick reference for MCP features
- **[MCP Implementation](MCP_IMPLEMENTATION_SUMMARY.md)** — Implementation details and technical notes
- **[MCP Feature Complete](MCP_FEATURE_COMPLETE.md)** — Full feature implementation summary

### 📂 Examples

- **Skills** — See `examples/skills/` for code-reviewer, test-writer, debugger
- **Agents** — See `examples/agents/` for explorer, planner, refactor
- **Hooks** — See `examples/hooks/` for safety and formatting hooks
- **MCP** — See `examples/mcp/` for MCP server configurations

---

## License

MIT © [Showdown Labs](https://github.com/showdownlabs)
