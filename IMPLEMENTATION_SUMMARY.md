# HTTP MCP Server Support Implementation - Summary

## Problem

You tried to run:
```bash
loco mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer TOKEN"}}'
```

But got the error:
```
Error: JSON configuration must contain 'command' field
```

This was because Loco only supported **command-based** MCP servers (local processes), not **HTTP-based** MCP servers.

## Solution Implemented

Added full support for HTTP-based MCP servers alongside the existing command-based servers.

## What Was Changed

### 1. Configuration Model (`src/loco/config.py`)
- Updated `MCPServerConfig` to support both types via a `type` discriminator field
- Added fields for HTTP config: `url` and `headers`
- Added validation to ensure proper fields based on type
- Changed type annotation for `mcp_servers` to accept dicts or model instances

### 2. HTTP Transport (`src/loco/mcp/transport.py`)
- Created new `HTTPTransport` class
- Implements MCP protocol over HTTP using POST requests and SSE
- Requires `aiohttp` (added as optional dependency)
- Supports custom headers for authentication

### 3. MCP Client (`src/loco/mcp/client.py`)
- Added `from_http()` factory method
- Added `from_config()` factory method to handle both types
- Unified interface for both transport types

### 4. Client Loader (`src/loco/mcp/loader.py`) - NEW FILE
- Created utility functions to load clients from config
- `load_mcp_clients()` - loads all configured servers
- `load_mcp_client(name)` - loads specific server

### 5. CLI Command (`src/loco/cli.py`)
- Updated `add-json` command to validate both config types
- Better error messages with examples for both types
- Uses Pydantic validation for type safety

### 6. Dependencies (`pyproject.toml`)
- Added `mcp-http` optional dependency group
- Includes `aiohttp>=3.8.0`

### 7. Documentation & Examples
- Updated `examples/mcp/README.md` with HTTP examples
- Updated `examples/mcp/config-with-mcp.json` with HTTP example
- Created `docs/HTTP_MCP_SUPPORT.md` with full documentation

## Usage Examples

### Add HTTP MCP Server (Your Use Case)
```bash
loco mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer TOKEN"}}'
```

### Add Command-based MCP Server
```bash
loco mcp add-json filesystem '{"type":"command","command":["npx","-y","@modelcontextprotocol/server-filesystem","/tmp"]}'
```

### Configuration File Format
```json
{
  "mcp_servers": {
    "github-copilot": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${GITHUB_COPILOT_TOKEN}"
      }
    },
    "filesystem": {
      "type": "command",
      "command": ["npx"],
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}
```

### Programmatic Usage
```python
from loco.config import load_config
from loco.mcp.loader import load_mcp_clients

config = load_config()
clients = load_mcp_clients(config)

for name, client in clients.items():
    print(f"{name}: {type(client.transport).__name__}")
```

## Key Features

1. **Type Safety**: Pydantic validation ensures configs are correct
2. **Backward Compatible**: Existing command-based configs still work
3. **Flexible**: Supports both local and remote MCP servers
4. **Extensible**: Easy to add more transport types in the future
5. **Well-Documented**: Examples and docs for both types

## Testing

All tests pass:
- ✅ Config validation for both types
- ✅ Client factory methods work
- ✅ Loading from config file works
- ✅ CLI command works
- ✅ Transport types instantiate correctly

## Files Changed

**Modified:**
- `src/loco/config.py` - Updated MCPServerConfig model
- `src/loco/mcp/transport.py` - Added HTTPTransport class
- `src/loco/mcp/client.py` - Added factory methods
- `src/loco/mcp/__init__.py` - Exported new classes/functions
- `src/loco/cli.py` - Updated add-json command
- `pyproject.toml` - Added aiohttp dependency
- `examples/mcp/README.md` - Added HTTP examples
- `examples/mcp/config-with-mcp.json` - Added HTTP example

**Created:**
- `src/loco/mcp/loader.py` - Client loading utilities
- `docs/HTTP_MCP_SUPPORT.md` - Full documentation

## Your Command Now Works! ✅

```bash
loco mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer YOUR_TOKEN_HERE"}}'
```

Output:
```
Added http-based MCP server 'github' to configuration
```

The server is now configured and ready to use!
