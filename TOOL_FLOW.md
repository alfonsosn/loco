# LoCo Tool Interaction Flow

This document visualizes how LoCo processes user requests and executes tools.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Prompt Toolkit + Rich Console                         │    │
│  │  • Input with history                                  │    │
│  │  • Streaming markdown output                           │    │
│  │  • Tool panels and spinners                            │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CLI Layer (cli.py)                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  • Parse slash commands                                │    │
│  │  • Handle /model, /skill, /agent, etc.                 │    │
│  │  • Pass regular chat to conversation handler           │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Conversation Layer (chat.py)                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  • Build message history                               │    │
│  │  • Add system prompts (base + skills)                  │    │
│  │  • Call LiteLLM with streaming                         │    │
│  │  • Parse tool calls from LLM response                  │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LiteLLM Integration                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  • Route to appropriate provider                       │    │
│  │  • Handle API keys and authentication                  │    │
│  │  • Stream response chunks                              │    │
│  │  • Retry with exponential backoff                      │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Provider (API)                           │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  OpenAI / Anthropic / Bedrock / Ollama / etc.          │    │
│  │  • Process request                                     │    │
│  │  • Generate tool calls                                 │    │
│  │  • Stream response                                     │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Tool Execution Flow                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Hook System (hooks.py)                                │    │
│  │  ├─ PreToolUse: Validate/log before execution          │    │
│  │  │                                                      │    │
│  │  Tool Registry (tools/base.py)                         │    │
│  │  ├─ Route to specific tool                             │    │
│  │  │                                                      │    │
│  │  Tool Implementations (tools/*.py)                     │    │
│  │  ├─ read, write, edit, bash, glob, grep                │    │
│  │  │                                                      │    │
│  │  Hook System (hooks.py)                                │    │
│  │  └─ PostToolUse: Format/enhance result                 │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Request Flow

### 1. User Input Processing

```
User Input: "Read chat.py and explain streaming"
                    │
                    ▼
         ┌──────────────────────┐
         │  Is slash command?   │
         └──────────────────────┘
              │         │
         YES  │         │  NO
              ▼         ▼
    ┌─────────────┐  ┌──────────────────┐
    │   Handle    │  │  Add to          │
    │   /model    │  │  conversation    │
    │   /skill    │  │  as user         │
    │   /agent    │  │  message         │
    └─────────────┘  └──────────────────┘
```

### 2. LLM Processing

```
Conversation → LiteLLM → LLM Provider
                    │
                    ▼
            ┌───────────────┐
            │  LLM decides  │
            │  to use tool? │
            └───────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
       YES                      NO
        │                       │
        ▼                       ▼
   ┌─────────────────┐    ┌──────────────┐
   │  Generate tool  │    │  Generate    │
   │  call with      │    │  text        │
   │  JSON params    │    │  response    │
   └─────────────────┘    └──────────────┘
        │                       │
        ▼                       ▼
   Execute tools          Display to user
```

### 3. Tool Execution Flow

```
Tool Call Received
        │
        ▼
┌────────────────────┐
│  PreToolUse Hooks  │
│  • Log command     │
│  • Validate params │
│  • Can block       │
└────────────────────┘
        │
        ▼
┌────────────────────┐
│  Tool Registry     │
│  • Lookup tool     │
│  • Validate exists │
└────────────────────┘
        │
        ▼
┌────────────────────┐
│  Execute Tool      │
│  • Run operation   │
│  • Catch errors    │
│  • Return string   │
└────────────────────┘
        │
        ▼
┌────────────────────┐
│  PostToolUse Hooks │
│  • Format output   │
│  • Add context     │
│  • Enhance result  │
└────────────────────┘
        │
        ▼
   Result → LLM
```

## Example: Multi-Tool Interaction

```
User: "Find all Python files in src/, search for 'TODO' comments, 
       and create a prioritized list"

┌──────────────────────────────────────────────────────────┐
│ Step 1: LLM decides to use glob tool                    │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Call: glob                                          │
│ Arguments: { "pattern": "src/**/*.py" }                  │
└──────────────────────────────────────────────────────────┘
        │
        ▼ [Execute]
┌──────────────────────────────────────────────────────────┐
│ Result: ["src/loco/chat.py", "src/loco/cli.py", ...]    │
└──────────────────────────────────────────────────────────┘
        │
        ▼ [Send to LLM]
┌──────────────────────────────────────────────────────────┐
│ Step 2: LLM decides to use grep tool                    │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Call: grep                                          │
│ Arguments: {                                             │
│   "pattern": "TODO",                                     │
│   "path": "src",                                         │
│   "glob": "**/*.py"                                      │
│ }                                                        │
└──────────────────────────────────────────────────────────┘
        │
        ▼ [Execute]
┌──────────────────────────────────────────────────────────┐
│ Result: [                                                │
│   "src/loco/chat.py:45: # TODO: Add caching",           │
│   "src/loco/tools/bash.py:23: # TODO: Sandbox",         │
│   ...                                                    │
│ ]                                                        │
└──────────────────────────────────────────────────────────┘
        │
        ▼ [Send to LLM]
┌──────────────────────────────────────────────────────────┐
│ Step 3: LLM synthesizes final response                  │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ Prioritized TODO List:                                   │
│                                                          │
│ High Priority:                                           │
│ • Add sandboxing to bash tool (security)                │
│                                                          │
│ Medium Priority:                                         │
│ • Implement caching for chat responses                  │
│                                                          │
│ Low Priority:                                            │
│ • Refactor tool registry for plugins                    │
└──────────────────────────────────────────────────────────┘
```

## Skill System Integration

```
User: "/skill code-reviewer"
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ Load Skill                                                 │
│ • Read examples/skills/code-reviewer/SKILL.md              │
│ • Parse YAML frontmatter                                   │
│ • Extract skill content                                    │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ Update System Prompt                                       │
│ Base Prompt + Skill Instructions                           │
│                                                            │
│ "You are a helpful coding assistant...                     │
│                                                            │
│  # Code Reviewer                                           │
│  You are an expert code reviewer. Follow these steps:     │
│  1. Understand the context...                             │
│  2. Check for issues...                                   │
│  ..."                                                      │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ All Subsequent Messages Use Enhanced Prompt               │
└────────────────────────────────────────────────────────────┘
```

## Agent System Flow

```
User: "/agent explorer find all API routes"
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ Create Isolated Agent Context                             │
│ • Load agent definition                                    │
│ • Create new Conversation instance                         │
│ • Restrict to allowed tools only                           │
│ • Use agent's specified model                             │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ Agent Execution Loop                                       │
│ ┌──────────────────────────────────────────────────────┐  │
│ │  User Task → Agent LLM → Tools → Results            │  │
│ │  (Multiple iterations until task complete)           │  │
│ └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ Summarize Agent Results                                    │
│ • Collect agent's final response                           │
│ • Add to main conversation as:                             │
│   User: "[Agent 'explorer' completed task]"                │
│   Assistant: "Agent result: ..."                           │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Main Conversation Continues
```

## Hook System Execution

```
                Tool Call Request
                        │
                        ▼
        ┌───────────────────────────────┐
        │     PreToolUse Hooks          │
        │  ┌─────────────────────────┐  │
        │  │  For each matching hook │  │
        │  │  • Execute command      │  │
        │  │  • Check exit code      │  │
        │  │  • If fail: block tool  │  │
        │  └─────────────────────────┘  │
        └───────────────────────────────┘
                        │
                    Success?
                        │
                  YES   │   NO
              ┌─────────┴──────────┐
              ▼                    ▼
      Execute Tool         Return Error
              │
              ▼
        ┌───────────────────────────────┐
        │    PostToolUse Hooks          │
        │  ┌─────────────────────────┐  │
        │  │  For each matching hook │  │
        │  │  • Execute command      │  │
        │  │  • Can modify result    │  │
        │  │  • Can add context      │  │
        │  └─────────────────────────┘  │
        └───────────────────────────────┘
                        │
                        ▼
              Enhanced Result → LLM
```

## Streaming Response Flow

```
LLM API (Streaming Mode)
        │
        ▼
┌───────────────────────────────────────┐
│  For each chunk received:             │
│                                       │
│  1. Parse chunk                       │
│  2. Check if tool call or text        │
│  3. Update Rich Live display          │
│  4. Accumulate full response          │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  Chunk Type?                          │
└───────────────────────────────────────┘
        │
    ┌───┴────┐
    │        │
  Text    Tool Call
    │        │
    ▼        ▼
Update     Parse JSON
Live       Arguments
Display    │
           ▼
        Execute
        Tool
           │
           ▼
        Stream
        Result
```

## Session Persistence

```
/save command
        │
        ▼
┌────────────────────────────────────────┐
│  Serialize Conversation                │
│  {                                     │
│    "session_id": "abc123",             │
│    "name": "auth-refactor",            │
│    "model": "openai/gpt-4o",           │
│    "messages": [                       │
│      {                                 │
│        "role": "system",               │
│        "content": "..."                │
│      },                                │
│      ...                               │
│    ],                                  │
│    "created_at": "2025-01-17...",      │
│    "updated_at": "2025-01-17..."       │
│  }                                     │
└────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────┐
│  Write to                              │
│  ~/.config/loco/history/abc123.json    │
└────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────┐
│  /load abc123                          │
│  • Read JSON file                      │
│  • Deserialize messages                │
│  • Restore conversation state          │
│  • Continue from where you left off    │
└────────────────────────────────────────┘
```

## Tool Registry Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Tool Registry                            │
│                                                             │
│  _tools = {                                                 │
│    "read": ReadTool(),                                      │
│    "write": WriteTool(),                                    │
│    "edit": EditTool(),                                      │
│    "bash": BashTool(),                                      │
│    "glob": GlobTool(),                                      │
│    "grep": GrepTool()                                       │
│  }                                                          │
│                                                             │
│  Methods:                                                   │
│  • register(tool)     - Add new tool                        │
│  • get(name)          - Lookup by name                      │
│  • get_all()          - List all tools                      │
│  • get_openai_tools() - Format for LiteLLM                  │
│  • execute(name, args) - Run tool with args                 │
└─────────────────────────────────────────────────────────────┘
```

## Complete User Journey Example

```
1. Start LoCo
   $ loco -m sonnet
   
2. Welcome screen displays
   ┌──────────────────────────────┐
   │ loco - LLM Coding Assistant  │
   │ Model: openai/claude-sonnet  │
   │ Working directory: ~/project │
   │ 3 skill(s), 3 agent(s) available │
   └──────────────────────────────┘

3. User asks question
   > Find TODO comments and create tickets

4. LLM generates tool calls
   [Tool: glob] pattern: "**/*.py"
   [Result: glob] Found 45 Python files...
   
   [Tool: grep] pattern: "TODO"
   [Result: grep] Found 12 matches...

5. LLM synthesizes response
   [Streaming markdown output]
   I found 12 TODO comments. Here's a prioritized list:
   
   **High Priority**
   1. Add authentication to API endpoints
   2. Fix memory leak in cache module
   ...

6. User continues conversation
   > Create GitHub issues for the high priority items
   
   [Tool: bash] command: "gh issue create..."
   [Result: bash] Created issue #42
   
   > /save todo-cleanup
   Saved as session: abc123

7. Later...
   $ loco
   > /load abc123
   Loaded session: abc123 (15 messages)
   > Let's continue...
```

## Key Takeaways

1. **Modular Design**: Each component has clear responsibilities
2. **Registry Pattern**: Enables dynamic tool/skill/agent discovery
3. **Hook System**: Provides extension points without modifying core
4. **Streaming**: Real-time feedback improves user experience
5. **LiteLLM**: Abstracts provider differences
6. **Rich UI**: Makes terminal interaction beautiful
7. **Session Management**: Enables long-running projects

---

This flow demonstrates how LoCo orchestrates multiple components to provide a seamless AI coding assistant experience in the terminal.
