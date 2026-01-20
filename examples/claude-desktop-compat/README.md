# Claude Desktop Compatibility Example

This example demonstrates using `.claude/` directories for seamless integration with Claude Desktop workflows.

## Overview

Loco supports **both** `.claude/` and `.loco/` directories for skills and agents, making it easy to share configurations between tools.

## Directory Structure

```
my-project/
├── .claude/              # Claude Desktop compatible
│   ├── skills/
│   │   └── code-style/
│   │       └── SKILL.md
│   └── agents/
│       └── reviewer.md
├── .loco/                # Loco native (takes precedence)
│   ├── skills/
│   │   └── testing/
│   │       └── SKILL.md
│   └── agents/
│       └── debugger.md
└── src/
```

## Precedence Order

When the same skill/agent exists in multiple locations:

1. `~/.config/loco/skills/` or `~/.config/loco/agents/` (lowest)
2. `.claude/skills/` or `.claude/agents/` (middle)
3. `.loco/skills/` or `.loco/agents/` (highest)

## Example: Shared Skill

Create `.claude/skills/code-style/SKILL.md`:

```markdown
---
name: code-style
description: Enforces project code style
allowed-tools: read, write, edit
user-invocable: true
---

# Code Style Enforcer

When writing or modifying code, follow these rules:

1. Python: Use type hints for all functions
2. JavaScript: Use ES6+ syntax
3. Format with project formatter (Ruff, Prettier, etc.)
4. Maximum line length: 100 characters
5. Use descriptive variable names

Apply these rules consistently across the codebase.
```

## Example: Project Agent

Create `.claude/agents/reviewer.md`:

```markdown
---
name: reviewer
description: Reviews code changes
tools: read, grep, glob
model: sonnet
---

# Code Reviewer Agent

You are a thorough code reviewer. When given code to review:

1. **Correctness**: Check for bugs and logic errors
2. **Style**: Verify adherence to project conventions
3. **Performance**: Identify potential bottlenecks
4. **Security**: Look for vulnerabilities
5. **Tests**: Ensure adequate test coverage

Provide specific, actionable feedback with line numbers and examples.
```

## Using Claude-Compatible Directories

### In Loco

```bash
# Skills from .claude/ are automatically discovered
loco
> /skills
code-style: Enforces project code style

# Activate a skill from .claude/
> /skill code-style
Activated skill: code-style

# Run an agent from .claude/
> /agent reviewer Please review src/auth.py
```

### In Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "loco": {
      "command": "loco",
      "args": ["mcp-server"],
      "cwd": "/path/to/my-project"
    }
  }
}
```

Both tools can now share the same skills and agents from `.claude/`!

## Benefits

✅ **Portability**: Share configurations between Loco and Claude Desktop  
✅ **Flexibility**: Override with `.loco/` when needed  
✅ **Familiarity**: Use familiar `.claude/` conventions  
✅ **No Migration**: Existing `.loco/` setups work unchanged

## Migration Guide

If you already have `.loco/` directories, you don't need to change anything!

To enable Claude Desktop compatibility:

```bash
# Option 1: Copy to .claude/
cp -r .loco/.claude/

# Option 2: Symlink (both tools see same files)
ln -s .loco/.claude

# Option 3: Keep both (use .loco/ for overrides)
# Just create .claude/ alongside .loco/
```

## Best Practices

1. **Shared Skills**: Put common, reusable skills in `.claude/`
2. **Tool-Specific**: Use `.loco/` for Loco-specific overrides
3. **Version Control**: Commit both directories for team sharing
4. **Documentation**: Add README in each directory explaining purpose

## Example Project Layout

```
# Shared between tools
.claude/
  skills/
    conventions/SKILL.md    # Team coding standards
    documentation/SKILL.md  # Doc writing guidelines
  agents/
    explorer.md             # Codebase navigation
    reviewer.md             # Code review

# Loco-specific (optional)
.loco/
  skills/
    testing/SKILL.md        # Override testing approach
  agents/
    debugger.md             # Custom debugging agent
```

This gives you maximum flexibility while maintaining compatibility!
