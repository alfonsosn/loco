# loco

A Claude Code-inspired CLI for any OpenAI-compatible LLM via LiteLLM.

## Features

- **Multi-provider support**: OpenAI, Amazon Bedrock, OpenRouter, Ollama, LM Studio, and any LiteLLM-supported provider
- **Streaming responses**: Real-time token streaming with markdown rendering
- **Built-in tools**: Read, Write, Edit, Bash, Glob, Grep
- **Skills system**: Reusable prompts that teach the LLM specific tasks
- **Hooks**: Shell commands at lifecycle events (pre/post tool use)
- **Session persistence**: Save and load conversations
- **Secure**: No external server - direct API calls only, config file permissions enforced
- **Model aliases**: Define shortcuts for frequently used models
- **Retry logic**: Automatic retries for transient API errors

## Installation

```bash
# From git
pip install git+https://github.com/yourusername/loco.git

# Or for development
git clone https://github.com/yourusername/loco.git
cd loco
pip install -e .
```

## Configuration

Config is stored at `~/.config/loco/config.json`. Created automatically on first run.

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
    },
    "openrouter": {
      "api_key": "${OPENROUTER_API_KEY}"
    }
  }
}
```

Environment variables are expanded (`${VAR}` syntax).

## Usage

```bash
# Start with default model
loco

# Use a specific model (alias or full name)
loco --model gpt4
loco --model bedrock/us.anthropic.claude-sonnet-4-20250514

# Start in a specific directory
loco --cwd /path/to/project
```

### Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/model [name]` | Show or switch current model |
| `/skill [name]` | Activate a skill or list available skills |
| `/skills` | List all available skills |
| `/clear` | Clear conversation history |
| `/save [name]` | Save current conversation |
| `/load <id>` | Load a saved conversation |
| `/sessions` | List saved sessions |
| `/config` | Show config file path |
| `/quit` | Exit (or Ctrl+C) |

## Supported Providers

Via LiteLLM, loco supports:

- **OpenAI**: `openai/gpt-4o`, `openai/gpt-4o-mini`
- **Amazon Bedrock**: `bedrock/us.anthropic.claude-sonnet-4-20250514`
- **OpenRouter**: `openrouter/anthropic/claude-3.5-sonnet`
- **Ollama**: `ollama/llama3`, `ollama/codellama`
- **LM Studio**: `lm_studio/local-model`
- **Azure OpenAI**: `azure/deployment-name`
- And [many more](https://docs.litellm.ai/docs/providers)

## Tools

loco includes these built-in tools:

- **read**: Read file contents with line numbers
- **write**: Create or overwrite files
- **edit**: Edit files via string replacement
- **bash**: Execute shell commands
- **glob**: Find files by pattern (e.g., `**/*.py`)
- **grep**: Search file contents with regex

## Skills

Skills are reusable prompts that teach the LLM specific tasks. They're loaded from:
- Project: `.loco/skills/skill-name/SKILL.md`
- User: `~/.config/loco/skills/skill-name/SKILL.md`

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

Instructions for the LLM when this skill is active...
```

### Using Skills

```bash
# List available skills
/skills

# Activate a skill
/skill code-reviewer

# Deactivate
/skill off
```

### Example Skills

See `examples/skills/` for ready-to-use skills:
- **code-reviewer**: Reviews code for quality and issues
- **test-writer**: Generates comprehensive tests
- **debugger**: Helps debug issues systematically

Copy them to `.loco/skills/` or `~/.config/loco/skills/` to use.

## Hooks

Hooks are shell commands that run at lifecycle events. They can validate, modify, or block tool calls.

### Hook Events

| Event | Description |
|-------|-------------|
| `PreToolUse` | Runs before a tool executes. Can approve/deny/modify. |
| `PostToolUse` | Runs after a tool executes. Can add context. |

### Configuration

Add hooks to `~/.config/loco/config.json`:

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

### Hook Input/Output

Hooks receive JSON on stdin:
```json
{
  "hook_event": "PreToolUse",
  "tool_name": "bash",
  "tool_input": { "command": "ls -la" },
  "cwd": "/current/dir"
}
```

Hooks output JSON on stdout (optional):
```json
{
  "decision": "deny",
  "reason": "Blocked dangerous command",
  "additional_context": "Extra info for the LLM"
}
```

Exit codes:
- `0`: Success (may include JSON output)
- `2`: Blocking error (stderr shown)
- Other: Non-blocking error

### Example Hooks

See `examples/hooks/` for ready-to-use hooks:
- **block-dangerous-commands.sh**: Blocks `rm -rf /`, fork bombs, etc.
- **format-on-write.sh**: Auto-formats files with black/prettier/gofmt
- **lint-on-write.sh**: Runs linters and reports issues

## License

MIT
