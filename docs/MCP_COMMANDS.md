# MCP CLI Commands Reference

Complete reference for managing MCP (Model Context Protocol) servers in Loco.

## Overview

The `loco mcp` command group provides tools to manage both command-based and HTTP-based MCP servers.

```bash
loco mcp [COMMAND] [OPTIONS]
```

## Commands

### `loco mcp list`

List all configured MCP servers with their types and details.

**Usage:**
```bash
loco mcp list
```

**Example Output:**
```
                    Configured MCP Servers                          
┏━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name         ┃ Type    ┃ Details                              ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ github       │ HTTP    │ https://api.github.com/mcp (1 hdr)   │
│ filesystem   │ COMMAND │ npx -y +2 arg(s)                     │
└──────────────┴─────────┴──────────────────────────────────────┘

Total: 2 server(s)
```

---

### `loco mcp add-json`

Add a new MCP server from JSON configuration.

**Usage:**
```bash
loco mcp add-json <name> '<json-config>'
```

**Examples:**

HTTP-based server:
```bash
loco mcp add-json github '{
  "type": "http",
  "url": "https://api.githubcopilot.com/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_TOKEN"
  }
}'
```

Command-based server:
```bash
loco mcp add-json filesystem '{
  "type": "command",
  "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem"],
  "args": ["/tmp"]
}'
```

With environment variables:
```bash
loco mcp add-json github-cli '{
  "type": "command",
  "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_TOKEN": "${GITHUB_TOKEN}"
  }
}'
```

---

### `loco mcp remove`

Remove an MCP server from configuration.

**Usage:**
```bash
loco mcp remove <name>
```

**Example:**
```bash
loco mcp remove github
# Output: ✓ Removed http-based MCP server 'github'
```

---

### `loco mcp show`

Show detailed configuration for an MCP server. Automatically masks sensitive data in headers (Authorization, tokens, etc.).

**Usage:**
```bash
loco mcp show <name>
```

**Example:**
```bash
loco mcp show github

# Output:
# MCP Server: github
# {
#   "type": "http",
#   "url": "https://api.githubcopilot.com/mcp",
#   "headers": {
#     "Authorization": "Bearer ghp..."
#   }
# }
```

---

### `loco mcp test`

Test connectivity and initialization of MCP server(s).

**Usage:**
```bash
# Test a specific server
loco mcp test <name> [--timeout SECONDS]

# Test all servers
loco mcp test [--timeout SECONDS]
```

**Options:**
- `--timeout` - Timeout in seconds for initialization (default: 10)

**Examples:**
```bash
# Test a specific server
loco mcp test github --timeout 5

# Test all configured servers
loco mcp test
```

**Example Output:**
```
Testing 2 server(s)...

✓ github: OK - 15 tool(s) available
✗ filesystem: Timeout after 10s
```

---

### `loco mcp tools`

List available tools from MCP server(s).

**Usage:**
```bash
# List tools from a specific server
loco mcp tools <name> [--timeout SECONDS]

# List tools from all servers
loco mcp tools [--timeout SECONDS]
```

**Options:**
- `--timeout` - Timeout in seconds (default: 10)

**Examples:**
```bash
# List tools from a specific server
loco mcp tools github

# List tools from all servers
loco mcp tools
```

**Example Output:**
```
Querying 1 server(s)...

                    Tools from 'github'
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Tool               ┃ Description                       ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ create_issue       │ Create a new GitHub issue         │
│ search_repositories│ Search for GitHub repositories    │
│ get_file_contents  │ Get contents of a file from repo  │
└────────────────────┴───────────────────────────────────┘
```

---

## Configuration Types

### HTTP-Based MCP Server

For remote HTTP/SSE MCP servers:

```json
{
  "type": "http",
  "url": "https://api.example.com/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_TOKEN",
    "X-Custom-Header": "value"
  }
}
```

**Required fields:**
- `type`: Must be `"http"`
- `url`: The HTTP endpoint for the MCP server

**Optional fields:**
- `headers`: Dictionary of HTTP headers (useful for authentication)

### Command-Based MCP Server

For local process-based MCP servers:

```json
{
  "type": "command",
  "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem"],
  "args": ["/path/to/directory"],
  "env": {
    "ENV_VAR": "value"
  },
  "cwd": "/working/directory"
}
```

**Required fields:**
- `type`: Must be `"command"` (or omit for default)
- `command`: Array of command parts (executable + flags)

**Optional fields:**
- `args`: Additional arguments (appended to command)
- `env`: Environment variables for the process
- `cwd`: Working directory for the process

---

## Common Workflows

### Adding a Server

1. Find the MCP server configuration
2. Add it using `add-json`:
   ```bash
   loco mcp add-json myserver '{"type":"http","url":"..."}'
   ```
3. Verify it was added:
   ```bash
   loco mcp list
   ```
4. Test connectivity:
   ```bash
   loco mcp test myserver
   ```
5. See available tools:
   ```bash
   loco mcp tools myserver
   ```

### Inspecting Configuration

```bash
# List all servers
loco mcp list

# Show specific server config
loco mcp show myserver

# See what tools are available
loco mcp tools myserver
```

### Removing a Server

```bash
# Remove the server
loco mcp remove myserver

# Verify it's gone
loco mcp list
```

### Testing Multiple Servers

```bash
# Test all servers at once
loco mcp test

# List all available tools
loco mcp tools
```

---

## Tips

1. **Use environment variables** for sensitive data:
   ```json
   {
     "headers": {
       "Authorization": "Bearer ${GITHUB_TOKEN}"
     }
   }
   ```

2. **Test after adding** to catch configuration errors early:
   ```bash
   loco mcp add-json myserver '...'
   loco mcp test myserver
   ```

3. **Check available tools** to understand what a server provides:
   ```bash
   loco mcp tools myserver
   ```

4. **Use show to debug** configuration issues (secrets are masked):
   ```bash
   loco mcp show myserver
   ```

---

## See Also

- [HTTP MCP Support Documentation](./HTTP_MCP_SUPPORT.md)
- [MCP Examples](../examples/mcp/)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
