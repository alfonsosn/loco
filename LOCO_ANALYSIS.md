# LoCo Analysis - TUI-Based AI Coding Assistant

## Overview

**LoCo** (LLM Coding) is a terminal-based (TUI) AI coding assistant inspired by Claude Code, designed to work with **any LLM provider** through LiteLLM. It offers a powerful, flexible alternative to proprietary coding assistants while maintaining full control over your data and infrastructure.

### Key Statistics
- **Language**: Python 3.11+
- **Lines of Code**: ~3,000 (highly modular)
- **Python Files**: 418 total
- **Dependencies**: Rich, LiteLLM, Click, Pydantic, Prompt Toolkit

## 🎯 Core Value Proposition

LoCo was created to solve a critical gap: **Claude Code's amazing coding capabilities, but with the freedom to use any LLM and maintain full control**.

### Why LoCo?

1. **Provider Freedom**: Use OpenAI, Anthropic (via Bedrock/OpenRouter), Ollama, LM Studio, or any of 100+ providers
2. **Open Source**: Fully transparent, auditable, extensible
3. **No Lock-in**: Direct API calls, no intermediary servers
4. **Local-First**: Your code never leaves your machine except for API calls you control
5. **Extensible**: Skills, agents, hooks for customization

## 🏗️ Architecture

### Component Breakdown

```
src/loco/
├── cli.py          # Main CLI entry point (~414 lines)
├── chat.py         # Conversation management & LiteLLM integration (~360 lines)
├── config.py       # Configuration management
├── history.py      # Session persistence
├── skills.py       # Skill system (reusable prompts)
├── agents.py       # Subagent system (isolated contexts)
├── hooks.py        # Pre/post tool execution hooks
├── tools/          # Built-in tools (read, write, edit, bash, glob, grep)
│   ├── base.py     # Tool abstraction & registry
│   └── *.py        # Individual tool implementations
└── ui/             # Rich-based TUI components
    ├── console.py  # Console wrapper with prompt toolkit
    └── components.py # UI panels, spinners, streaming
```

### Design Patterns

1. **Registry Pattern**: Tools, Skills, and Agents use registries for dynamic discovery
2. **Strategy Pattern**: Hook system for customizable tool execution
3. **Command Pattern**: Slash commands for interactive control
4. **Streaming**: Real-time LLM response streaming with Rich Live
5. **Context Management**: Clean resource handling with Python context managers

## 🛠️ Feature Deep Dive

### 1. Tool System

LoCo provides 6 built-in tools that give the LLM powerful file system and code interaction capabilities:

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `read` | Read files | Line numbers, offset/limit for large files |
| `write` | Create/overwrite files | Automatic directory creation |
| `edit` | String replacement | Precise edits without full file rewrites |
| `bash` | Execute commands | Timeout protection, real-time output |
| `glob` | Find files | Standard glob patterns (`**/*.py`) |
| `grep` | Search content | Regex support, context lines, case options |

**Tool Architecture**:
```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]: ...
    
    @abstractmethod
    def execute(self, **kwargs: Any) -> str: ...
    
    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI tool format for LiteLLM."""
```

Tools automatically convert to OpenAI's function calling format, making them compatible with any LLM that supports tool use.

### 2. Skills System

**Skills** are reusable prompt templates that teach the LLM specific tasks. They're Markdown files with YAML frontmatter:

```markdown
---
name: code-reviewer
description: Reviews code for quality
allowed-tools: read, grep, glob
user-invocable: true
---

# Code Reviewer
You are an expert code reviewer...
```

**Key Features**:
- **Tool Restrictions**: Limit which tools a skill can use
- **User Invocable**: Control which skills appear in `/skill` command
- **System Prompt Injection**: Skills modify the LLM's behavior
- **Discovery**: Auto-loaded from `.loco/skills/` and `~/.config/loco/skills/`

**Example Skills** (included):
- `code-reviewer`: Reviews PRs and code quality
- `test-writer`: Generates comprehensive tests
- `debugger`: Analyzes and fixes bugs

### 3. Agent System

**Agents** are isolated subagents with their own:
- System prompt
- Tool restrictions
- Separate model (e.g., use Haiku for fast exploration, Sonnet for main work)
- Independent conversation context

```markdown
---
name: explorer
description: Fast codebase exploration
tools: read, glob, grep
model: haiku
---

# Explorer Agent
You quickly find information in codebases...
```

**Use Cases**:
- **Explorer**: Fast file/code search with a cheaper model
- **Planner**: Analyze requirements before implementation
- **Refactor**: Focused refactoring without polluting main context

**Agent Execution**:
```bash
/agent explorer find all authentication routes
```

Results are summarized back to the main conversation.

### 4. Hooks System

Hooks allow running shell scripts at lifecycle events:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "bash",
      "hooks": [{ "type": "command", "command": "./validate.sh" }]
    }],
    "PostToolUse": [{
      "matcher": "write",
      "hooks": [{ "type": "command", "command": "ruff format {file}" }]
    }]
  }
}
```

**Hook Types**:
- **PreToolUse**: Validate before execution (can block)
- **PostToolUse**: Post-process results (can add context)

**Examples**:
- Format code after writing
- Validate bash commands before execution
- Run tests after code changes
- Add git status to context

### 5. Session Management

Conversations can be saved and resumed:

```bash
/save my-feature-work       # Save with a name
/sessions                   # List all sessions
/load abc123                # Resume a session
```

**Storage**: `~/.config/loco/history/` as JSON files

**Features**:
- Preserves full message history
- Includes model information
- Auto-save support (planned)
- Named sessions for organization

## 🎨 TUI Design

### Console Components

1. **Welcome Screen**: Shows model, working directory, available skills/agents
2. **Input Prompt**: Prompt Toolkit with history and auto-completion
3. **Tool Panels**: Highlighted tool calls with bordered panels
4. **Streaming Markdown**: Real-time LLM responses with markdown rendering
5. **Result Panels**: Color-coded tool results (green=success, red=error)

### Rich Integration

LoCo uses Rich for beautiful terminal output:
- **Markdown Rendering**: Properly formatted code blocks, lists, headers
- **Syntax Highlighting**: Monokai theme for code
- **Panels**: Bordered sections for tool calls/results
- **Spinners**: "Thinking..." indicators during API calls
- **Live Updates**: Streaming text without flicker

### Prompt Toolkit Features

- **History**: Persistent command history across sessions
- **Multi-line Support**: Ctrl+Enter for multi-line input
- **Keyboard Shortcuts**: Standard readline bindings
- **Custom Styling**: Cyan prompt indicator

## 🔧 Configuration System

### Config File Location
`~/.config/loco/config.json`

### Structure

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
  },
  "hooks": { ... }
}
```

### Key Features

1. **Model Aliases**: Short names for long model strings
2. **Environment Variables**: `${VAR}` expansion for secrets
3. **Multiple Providers**: Configure different API keys/regions
4. **Per-Provider Settings**: AWS regions, API bases, etc.

### LiteLLM Integration

LoCo uses LiteLLM for provider abstraction:
- **100+ Providers**: OpenAI, Anthropic, Cohere, Azure, Bedrock, Ollama, etc.
- **Unified API**: Single interface for all providers
- **Automatic Retries**: Exponential backoff on failures
- **Parameter Dropping**: Handles provider-specific quirks

## 🚀 Usage Patterns

### Basic Interaction

```bash
$ loco
> Read the main chat file and explain how streaming works

[Tool: read]
  file_path: "src/loco/chat.py"

[Result: read]
[... file content ...]

[Assistant Response]
The streaming implementation uses LiteLLM's completion() with stream=True...
```

### Model Switching

```bash
> /model                    # Show current model
> /model haiku              # Switch to alias
> /model openai/gpt-4o      # Switch to full model name
```

### Skill Activation

```bash
> /skills                   # List available
> /skill code-reviewer      # Activate
> Review the chat.py file   # Skill guides behavior
> /skill off                # Deactivate
```

### Agent Delegation

```bash
> /agent explorer find all route definitions in the project

[Agent 'explorer' running...]
[Agent result:]
Found 23 routes across 5 files:
- src/api/auth.py: /login, /logout, /register
- src/api/users.py: /users, /users/{id}
...
```

### Session Management

```bash
> /save refactoring-work    # Save current work
> /sessions                 # List all sessions
> /load abc123              # Resume later
```

## 💡 Advanced Features

### 1. System Prompt Engineering

LoCo's default system prompt is carefully crafted:

```python
def get_default_system_prompt(cwd: str, skills_section: str = "") -> str:
    return f"""You are a helpful coding assistant...

You have access to a set of tools you can use to answer the user's question.
...
Current working directory: {cwd}
...
{skills_section}
"""
```

Key elements:
- **Tool descriptions**: Explicitly list each tool's purpose
- **Guidelines**: How to use tools effectively
- **Context**: Current working directory
- **Skills**: Injected dynamically when activated

### 2. Retry Logic with Exponential Backoff

```python
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # multiplier

# Automatic retry on rate limits, network errors
```

### 3. Token Budget Awareness

LoCo is designed to be token-efficient:
- Truncates long tool results (>50 lines)
- Provides line numbers for precise edits
- Uses `edit` instead of full rewrites
- Streams responses (reduces perceived latency)

### 4. Security Features

- **No external servers**: Direct API calls only
- **Configurable hooks**: Validate dangerous commands
- **Tool restrictions**: Skills/agents can limit available tools
- **Local execution**: All tools run in your environment

## 🔬 Code Quality Observations

### Strengths

1. **Clean Architecture**: Well-separated concerns (tools, UI, config, chat)
2. **Type Hints**: Full type annotations for better IDE support
3. **Error Handling**: Comprehensive try-except blocks with user-friendly messages
4. **Modularity**: Easy to add new tools, skills, agents
5. **Testing**: Pytest setup with async support

### Areas for Enhancement

1. **Test Coverage**: Only basic test structure present
2. **Async Support**: Could benefit from async tool execution
3. **Caching**: No caching of file reads or LLM responses
4. **Logging**: Limited logging for debugging
5. **Configuration Validation**: Basic Pydantic validation could be expanded

## 🎓 Learning Points for Users

### For Developers

1. **Tool Design**: How to build LLM tools with proper JSON Schema
2. **Rich TUI**: Beautiful terminal UIs with Rich library
3. **LiteLLM Integration**: Multi-provider LLM abstraction
4. **Prompt Engineering**: System prompt design for coding tasks

### For Users

1. **Effective Prompting**: How to get the best results from coding LLMs
2. **Workflow Optimization**: Using skills and agents for complex tasks
3. **Tool Composition**: Combining glob, grep, read for exploration
4. **Session Management**: Organizing work across multiple conversations

## 🛣️ Potential Future Enhancements

Based on the codebase structure, natural extensions could include:

1. **MCP Integration**: Add Model Context Protocol support for external tools
2. **Web UI**: Optional Gradio/Streamlit interface alongside TUI
3. **Git Integration**: Built-in git tools (diff, commit, branch)
4. **Code Analysis**: AST-based tools for refactoring
5. **RAG Support**: Codebase indexing for better context
6. **Collaborative Features**: Share skills/agents with team
7. **Telemetry**: Optional usage analytics for optimization
8. **IDE Integration**: LSP server or editor plugins

## 📊 Comparison with Alternatives

| Feature | LoCo | Claude Code | Cursor | Aider |
|---------|------|-------------|--------|-------|
| Open Source | ✅ | ❌ | ❌ | ✅ |
| Multi-LLM | ✅ | ❌ | ❌ | ✅ |
| TUI | ✅ | ❌ | ❌ | ✅ |
| Skills System | ✅ | ❌ | ❌ | ❌ |
| Agent System | ✅ | ❌ | ❌ | ❌ |
| Hooks | ✅ | ❌ | ❌ | ❌ |
| IDE Integration | ❌ | ✅ | ✅ | ❌ |
| GUI | ❌ | ✅ | ✅ | ❌ |

## 🎯 Ideal Use Cases

1. **Terminal Enthusiasts**: Developers who live in the terminal
2. **Multi-Cloud Teams**: Need flexibility across LLM providers
3. **Privacy-Conscious**: Want control over data and API calls
4. **Power Users**: Need customization (skills, agents, hooks)
5. **Open Source Advocates**: Want transparency and extensibility

## 🏁 Conclusion

LoCo represents a thoughtful approach to AI coding assistance:
- **Flexible**: Works with any LLM provider
- **Powerful**: Rich tool set and extensibility
- **Beautiful**: Modern TUI with Rich
- **Open**: Fully transparent and customizable
- **Practical**: Designed for real-world coding workflows

The codebase is well-structured, maintainable, and ready for community contributions. With ~3,000 lines of clean Python, it demonstrates that you don't need massive complexity to build a useful AI coding assistant.

## 📚 References

- **Repository**: https://github.com/showdownlabs/loco
- **LiteLLM Docs**: https://docs.litellm.ai/
- **Rich Docs**: https://rich.readthedocs.io/
- **Prompt Toolkit**: https://python-prompt-toolkit.readthedocs.io/

---

*Analysis generated: January 2025*
*LoCo Version: 0.1.0*
