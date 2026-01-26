<div align="center">

# 🚂 loco

**Your AI coding assistant, any LLM, anywhere.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*A Claude Code-inspired CLI that works with OpenAI, Bedrock, Ollama, and 100+ LLM providers via LiteLLM.*

</div>

---

## ⚡ Quick Start

```bash
# Install with pipx (recommended)
pipx install git+https://github.com/showdownlabs/loco.git

# Or install with pip
pip install git+https://github.com/showdownlabs/loco.git

# Run
loco
```

That's it. Loco creates a config file on first run at `~/.config/loco/config.toml`.

See [Installation Guide](docs/installation.md) for more options.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔌 **100+ Providers** | OpenAI, Bedrock, OpenRouter, Ollama, LM Studio, Azure, and more |
| 🛠️ **Built-in Tools** | Read, Write, Edit, Bash, Glob, Grep |
| 🔗 **MCP Support** | Model Context Protocol server & client |
| 🎯 **Skills** | Reusable prompts for specific tasks |
| 🪝 **Hooks** | Pre/post tool execution scripts |
| 🤖 **Agents** | Subagents with isolated contexts |
| 💾 **Sessions** | Save and resume conversations |
| 🔒 **Secure** | No external server, direct API calls only |

---

## 🎬 Usage

```bash
loco                    # Start with default model
loco -m gpt4            # Use a model alias
loco -m openai/gpt-4o   # Use full model name
loco -C ~/projects/app  # Start in specific directory
```

### Slash Commands

```
/help              Show help
/model [name]      Switch or show model
/skill [name]      Activate a skill
/agent <n> <task>  Run a subagent
/save [name]       Save conversation
/load <id>         Load conversation
/clear             Clear history
/quit              Exit
```

---

## ⚙️ Configuration

`~/.config/loco/config.json`:

```json
{
  "default_model": "openai/gpt-4o",
  "models": {
    "gpt4": "openai/gpt-4o",
    "sonnet": "bedrock/us.anthropic.claude-sonnet-4-20250514",
    "local": "ollama/llama3"
  },
  "providers": {
    "openai": { "api_key": "${OPENAI_API_KEY}" },
    "bedrock": { "aws_region": "us-west-2" }
  }
}
```

> 💡 Use `${VAR}` syntax for environment variables.

---

## 🛠️ Tools

Loco includes 6 built-in tools:

| Tool | Description |
|------|-------------|
| `read` | Read files with line numbers |
| `write` | Create or overwrite files |
| `edit` | String replacement editing |
| `bash` | Execute shell commands |
| `glob` | Find files by pattern (`**/*.py`) |
| `grep` | Search file contents with regex |

**MCP Integration:** Loco can also connect to external MCP servers to access additional tools (databases, APIs, etc.). See [docs/MCP.md](docs/MCP.md).

---

## 🎯 Skills

Skills are reusable prompts that teach the LLM specific tasks.

**Location:** `.loco/skills/`, `.claude/skills/` (Claude Desktop compatible), or `~/.config/loco/skills/`

```markdown
---
name: code-reviewer
description: Reviews code for quality
allowed-tools: read, grep, glob
user-invocable: true
---

# Code Reviewer
You review code for quality and best practices...
```

```bash
/skills            # List skills
/skill reviewer    # Activate
/skill off         # Deactivate
```

**Examples:** See `examples/skills/` for code-reviewer, test-writer, debugger.

---

## 🪝 Hooks

Hooks run shell commands at lifecycle events.

| Event | When |
|-------|------|
| `PreToolUse` | Before tool runs (can block) |
| `PostToolUse` | After tool runs (can add context) |

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "bash",
      "hooks": [{ "type": "command", "command": "./validate.sh" }]
    }]
  }
}
```

**Examples:** See `examples/hooks/` for safety and formatting hooks.

---

## 🤖 Agents

Agents are subagents with isolated contexts and restricted tools.

**Location:** `.loco/agents/`, `.claude/agents/` (Claude Desktop compatible), or `~/.config/loco/agents/`

```markdown
---
name: explorer
description: Fast codebase exploration
tools: read, glob, grep
model: haiku
---

# Explorer
You quickly find information in codebases...
```

```bash
/agents                          # List agents
/agent explorer find API routes  # Run agent
```

**Examples:** See `examples/agents/` for explorer, planner, refactor.

---

## 🔗 MCP (Model Context Protocol)

Loco supports MCP both as a server and a client:

**As MCP Server:** Expose loco's tools to other MCP clients like Claude Desktop.

```bash
loco mcp-server
```

**As MCP Client:** Connect to external MCP servers to expand capabilities.

```json
{
  "mcp_servers": {
    "github": {
      "command": ["npx"],
      "args": ["-y", "@modelcontextprotocol/server-github"]
    }
  }
}
```

**Learn more:** [docs/MCP.md](docs/MCP.md) | [examples/mcp/](examples/mcp/)

---

## 📦 Supported Providers

Via [LiteLLM](https://docs.litellm.ai/docs/providers):

- **OpenAI** — `openai/gpt-4o`
- **Amazon Bedrock** — `bedrock/us.anthropic.claude-sonnet-4-20250514`
- **OpenRouter** — `openrouter/anthropic/claude-3.5-sonnet`
- **Ollama** — `ollama/llama3`
- **LM Studio** — `lm_studio/local-model`
- **Azure** — `azure/deployment-name`
- **And 100+ more...**

---

## 🔧 Development

```bash
git clone https://github.com/showdownlabs/loco.git
cd loco
pip install -e .
```

---

## 📚 Documentation

For comprehensive guides and documentation, see:

- **[Full Documentation](https://showdownlabs.github.io/loco/)** — Complete docs site
- **[Quick Start Guide](docs/QUICKSTART.md)** — Hands-on examples and workflows
- **[Architecture Guide](docs/ARCHITECTURE.md)** — How loco works under the hood
- **[Technical Analysis](docs/ANALYSIS.md)** — Deep dive into design and implementation
- **[MCP Guide](docs/MCP.md)** — Model Context Protocol integration

---

## 📄 License

MIT © [Showdown Labs](https://github.com/showdownlabs)
