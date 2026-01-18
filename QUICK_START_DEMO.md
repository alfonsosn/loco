# LoCo Quick Start Demo

This guide shows you how to get the most out of LoCo with practical examples.

## Installation

```bash
# Install from GitHub
pip install git+https://github.com/showdownlabs/loco.git

# Or install in development mode
git clone https://github.com/showdownlabs/loco.git
cd loco
pip install -e .
```

## Initial Setup

1. **First run** - LoCo creates `~/.config/loco/config.json` automatically
2. **Configure your API keys**:

```json
{
  "default_model": "openai/gpt-4o",
  "models": {
    "gpt4": "openai/gpt-4o",
    "sonnet": "anthropic/claude-sonnet-4",
    "haiku": "anthropic/claude-haiku-4", 
    "local": "ollama/codellama"
  },
  "providers": {
    "openai": {
      "api_key": "${OPENAI_API_KEY}"
    },
    "anthropic": {
      "api_key": "${ANTHROPIC_API_KEY}"
    }
  }
}
```

3. **Set environment variables**:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Basic Usage

### Starting LoCo

```bash
# Start with default model
loco

# Start with specific model
loco -m sonnet

# Start in a specific directory
loco -C ~/projects/my-app
```

## Example Workflows

### 1. Understanding a Codebase

```
> Use glob to find all Python files in src/

[LoCo executes: glob("src/**/*.py")]

> Now grep for class definitions

[LoCo executes: grep("^class ", "src/**/*.py")]

> Read the main chat.py file and explain how streaming works

[LoCo executes: read("src/loco/chat.py")]
[Explains the streaming implementation]
```

**Pro Tip**: The LLM will automatically chain tool calls. Just describe what you want!

### 2. Making Code Changes

```
> I need to add a new feature to handle rate limiting. 
  First, read the current chat.py implementation.

[LoCo reads the file]

> Now add exponential backoff logic after line 18. 
  The retry delay should be configurable.

[LoCo uses edit() to insert new code]

> Run the tests to make sure it works

[LoCo executes: bash("pytest tests/test_chat.py")]
```

**Pro Tip**: Use `edit` instead of `write` for precise changes. It's more token-efficient!

### 3. Using Skills for Code Review

```
> /skills

Available Skills:
  code-reviewer: Reviews code for quality
  test-writer: Generates comprehensive tests  
  debugger: Analyzes and fixes bugs

> /skill code-reviewer

Activated skill: code-reviewer

> Review the new rate limiting code I just added

[LoCo analyzes with code review focus]

### Summary
The rate limiting implementation looks good...

### Issues Found
**Minor**: Consider extracting magic numbers to constants
...

> /skill off
```

**Pro Tip**: Skills modify the system prompt to guide the LLM's behavior. Use them for specialized tasks!

### 4. Using Agents for Exploration

```
> /agents

Available Agents:
  explorer: Fast codebase exploration (tools: read, glob, grep)
  planner: Analyze requirements before implementation
  refactor: Focused refactoring assistant

> /agent explorer find all API route definitions

[Agent 'explorer' running with model: haiku]

[Tool: glob] Find route files...
[Tool: grep] Search for route decorators...
[Tool: read] Read route definitions...

Agent result:

Found 15 API routes across 3 files:

**src/api/auth.py**:
- POST /api/auth/login
- POST /api/auth/logout
- POST /api/auth/register

**src/api/users.py**:
- GET /api/users
- GET /api/users/{id}
- POST /api/users
- PUT /api/users/{id}
- DELETE /api/users/{id}

...

> Great! Now help me add rate limiting to all POST routes
```

**Pro Tip**: Agents use separate contexts and can use cheaper models (like Haiku) for fast exploration!

### 5. Complex Multi-Step Tasks

```
> I need to refactor the authentication system to use JWT tokens. 
  Here's what I need:
  
  1. First, analyze the current auth implementation
  2. Create a new jwt_utils.py module
  3. Update the auth routes to use JWT
  4. Add tests for the new functionality
  5. Update the documentation

Let's do this step by step. Start by reading the current auth code.

[LoCo proceeds step by step with your guidance]
```

**Pro Tip**: For complex tasks, break them into steps and guide LoCo through each one.

### 6. Using Hooks for Automation

Add to `~/.config/loco/config.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "write",
        "hooks": [
          {
            "type": "command",
            "command": "ruff format {file}",
            "description": "Auto-format Python files"
          }
        ]
      },
      {
        "matcher": "edit",
        "hooks": [
          {
            "type": "command", 
            "command": "ruff check {file}",
            "description": "Lint after editing"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Running: {command}'",
            "description": "Log bash commands"
          }
        ]
      }
    ]
  }
}
```

Now every file write/edit will be auto-formatted!

**Pro Tip**: Use hooks to integrate with your existing development workflow.

### 7. Session Management

```
> /save auth-refactor

Saved as session: abc123

[... later ...]

> /sessions

Saved Sessions:
  abc123 (auth-refactor) - 45 msgs, openai/gpt-4o
  def456 (bug-fix) - 12 msgs, anthropic/claude-sonnet-4
  ghi789 - 8 msgs, ollama/codellama

> /load abc123

Loaded session: abc123 (45 messages)

> Let's continue with the JWT implementation...
```

**Pro Tip**: Save sessions for complex features that span multiple days!

## Slash Commands Reference

```
/help              Show all commands
/model [name]      Switch models mid-conversation
/skill [name]      Activate a skill (or /skill off)
/skills            List available skills
/agent <name> <task>  Delegate to an agent
/agents            List available agents  
/save [name]       Save current session
/load <id>         Resume a session
/sessions          List all saved sessions
/config            Show config file location
/clear             Clear conversation history
/quit              Exit LoCo
```

## Tips & Tricks

### 1. Efficient File Exploration

Instead of reading entire files:
```
> Use grep to find the authentication function, then read just those lines
```

LoCo will use line numbers to read only relevant sections!

### 2. Iterative Development

```
> Make the change
[Edit code]

> Now test it
[Run tests]

> Fix the error  
[Edit again]

> Test again
[Run tests]
```

The conversation context helps LoCo understand the iterative process.

### 3. Switch Models for Different Tasks

```
> /model haiku               # Fast model for exploration
> What files handle auth?

> /model sonnet              # Powerful model for implementation  
> Now refactor the auth system to use JWT
```

### 4. Use Local Models for Privacy

```
> /model local               # Uses ollama/codellama
> Read the API keys from config and explain the auth flow
```

Local models keep sensitive code on your machine!

### 5. Combine Tools Effectively

LoCo is smart about chaining tools:

```
> Find all TODO comments, read those files, and create a prioritized list

[Executes: grep("TODO", "**/*.py")]
[Executes: read() for relevant files]  
[Creates prioritized list]
```

### 6. Project-Specific Skills

Create `.loco/skills/project-conventions.md`:

```markdown
---
name: project-conventions
description: Follow this project's coding standards
user-invocable: true
---

# Project Conventions

This project uses:
- Python 3.11+ with type hints
- Ruff for formatting
- Pytest for testing
- Google-style docstrings

Always follow these conventions when generating code.
```

Then: `/skill project-conventions`

## Troubleshooting

### "Error loading config"

```bash
# Reset config to defaults
rm ~/.config/loco/config.json
loco
```

### "Model not found"

```bash
# Check available models
loco
> /model

# Verify LiteLLM model format
# OpenAI: openai/gpt-4o
# Anthropic: anthropic/claude-sonnet-4
# Bedrock: bedrock/anthropic.claude-v2
# Ollama: ollama/llama2
```

### "API key error"

```bash
# Check environment variables
env | grep API_KEY

# Or hardcode in config (not recommended)
{
  "providers": {
    "openai": {
      "api_key": "sk-..."  // Instead of ${OPENAI_API_KEY}
    }
  }
}
```

### Rate Limiting

LoCo has built-in retry logic with exponential backoff:
- 3 retries by default
- 1s initial delay
- 2x backoff multiplier

For heavy usage, consider:
1. Using a local model with Ollama
2. Switching to a faster/cheaper model
3. Adding caching via hooks

## Next Steps

1. **Explore the examples**: Check out `examples/skills/` and `examples/agents/`
2. **Create custom skills**: Add your own reusable prompts
3. **Try different models**: Experiment with various providers
4. **Set up hooks**: Automate your workflow
5. **Join the community**: Contribute to the GitHub repo!

## Resources

- GitHub: https://github.com/showdownlabs/loco
- Issues: https://github.com/showdownlabs/loco/issues
- LiteLLM Models: https://docs.litellm.ai/docs/providers

---

Happy coding with LoCo! 🚂
