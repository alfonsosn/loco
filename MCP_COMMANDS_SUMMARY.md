# MCP CLI Commands - Implementation Summary

## Overview

Added 5 new commands to the `loco mcp` command group to make managing MCP servers easier and more intuitive.

## Commands Added

### 1. `loco mcp list`
**Purpose:** List all configured MCP servers

**Features:**
- Beautiful table display with Rich
- Shows server type (HTTP/COMMAND)
- Shows relevant details (URL for HTTP, command for Command-based)
- Displays total count

**Example:**
```bash
$ loco mcp list
                    Configured MCP Servers                          
┏━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name        ┃ Type    ┃ Details                              ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ github      │ HTTP    │ https://api.github.com/mcp (1 hdr)   │
│ filesystem  │ COMMAND │ npx -y +2 arg(s)                     │
└─────────────┴─────────┴─────────────────────────────────────┘

Total: 2 server(s)
```

---

### 2. `loco mcp show <name>`
**Purpose:** Show detailed configuration for a specific server

**Features:**
- Displays full JSON configuration
- **Automatically masks sensitive data** in headers (Authorization, tokens, keys, secrets, passwords)
- Easy to debug configuration issues
- Pretty-printed JSON output

**Example:**
```bash
$ loco mcp show github

MCP Server: github
{
  "type": "http",
  "url": "https://api.githubcopilot.com/mcp",
  "headers": {
    "Authorization": "Bearer ghp..."  ← Masked!
  }
}
```

---

### 3. `loco mcp remove <name>`
**Purpose:** Remove an MCP server from configuration

**Features:**
- Safe deletion with confirmation message
- Shows server type in confirmation
- Updates config file immediately
- Error handling for non-existent servers

**Example:**
```bash
$ loco mcp remove github
✓ Removed http-based MCP server 'github'
```

---

### 4. `loco mcp test [name]`
**Purpose:** Test connectivity and initialization of MCP server(s)

**Features:**
- Test a specific server or all servers
- Configurable timeout (default: 10s)
- Initializes connection and lists available tools
- Shows clear success/failure status
- Async operation with proper cleanup

**Usage:**
```bash
# Test specific server
$ loco mcp test github --timeout 5

# Test all servers
$ loco mcp test
```

**Example Output:**
```bash
Testing 2 server(s)...

✓ github: OK - 15 tool(s) available
✗ filesystem: Timeout after 10s
```

---

### 5. `loco mcp tools [name]`
**Purpose:** List available tools from MCP server(s)

**Features:**
- Query a specific server or all servers
- Beautiful table display of tools
- Shows tool names and descriptions
- Configurable timeout
- Truncates long descriptions for readability

**Usage:**
```bash
# List tools from specific server
$ loco mcp tools github

# List tools from all servers
$ loco mcp tools
```

**Example Output:**
```bash
Querying 1 server(s)...

                Tools from 'github'
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool            ┃ Description                    ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ create_issue    │ Create a new GitHub issue      │
│ search_repos    │ Search for repositories        │
│ get_file        │ Get contents of a file         │
└─────────────────┴────────────────────────────────┘
```

---

## Implementation Details

### Files Modified

**src/loco/cli.py** - Added 5 new commands (~250 lines)
- `list_servers()` - Lists all servers
- `remove()` - Removes a server
- `show()` - Shows server configuration
- `test()` - Tests server connectivity
- `tools()` - Lists available tools

### Key Features

1. **Type Safety** - Validates config before operations
2. **Error Handling** - Clear error messages for common issues
3. **Async Support** - Proper async/await for server communication
4. **Security** - Masks sensitive data in output
5. **UX** - Beautiful Rich tables and clear status indicators
6. **Flexibility** - Works with both command-based and HTTP servers

### Bug Fixes

- Fixed shadowing of built-in `list` type by renaming function to `list_servers()`

---

## Complete Command Reference

```bash
loco mcp list                      # List all servers
loco mcp add-json <name> '<json>'  # Add new server
loco mcp remove <name>             # Remove server
loco mcp show <name>               # Show config (masks secrets)
loco mcp test [name] [--timeout N] # Test connectivity
loco mcp tools [name] [--timeout N]# List available tools
```

---

## Common Workflows

### Quick Setup
```bash
# Add a server
loco mcp add-json github '{"type":"http","url":"..."}'

# Verify it's added
loco mcp list

# Test it works
loco mcp test github

# See what tools are available
loco mcp tools github
```

### Debugging
```bash
# List all servers
loco mcp list

# Inspect configuration
loco mcp show myserver

# Test connectivity
loco mcp test myserver
```

### Cleanup
```bash
# Remove a server
loco mcp remove oldserver

# Verify it's gone
loco mcp list
```

---

## Documentation Created

1. **docs/MCP_COMMANDS.md** - Complete command reference with examples
2. **scripts/demo_mcp_commands.py** - Interactive demo script

---

## Benefits

1. **Discoverability** - Easy to see what's configured
2. **Debugging** - Quick way to inspect and test servers
3. **Safety** - Masks sensitive data automatically
4. **Productivity** - Fast management of MCP servers
5. **User-Friendly** - Clear output with Rich formatting

---

## Testing

All commands tested and working:
- ✅ `loco mcp list` - Shows servers correctly
- ✅ `loco mcp add-json` - Adds servers (already existed)
- ✅ `loco mcp remove` - Removes servers safely
- ✅ `loco mcp show` - Displays config with masked secrets
- ✅ `loco mcp test` - Tests connectivity (async)
- ✅ `loco mcp tools` - Lists tools (async)

---

## What Users Can Do Now

Before:
```bash
# Had to manually edit ~/.config/loco/config.json
# No way to see what's configured without opening file
# No way to test if servers work
# No visibility into available tools
```

After:
```bash
# See all servers at a glance
loco mcp list

# Quick add/remove
loco mcp add-json name '...'
loco mcp remove name

# Debug config issues
loco mcp show name

# Test connectivity
loco mcp test name

# Discover tools
loco mcp tools name
```

Much better developer experience! 🎉
