# HTTP MCP Server Support

This document describes the HTTP MCP server support added to Loco.

## Overview

Loco now supports both **command-based** and **HTTP-based** MCP servers:

- **Command-based**: Local processes spawned by Loco (original functionality)
- **HTTP-based**: Remote HTTP/SSE MCP servers (new feature)

## Usage

### Adding an HTTP MCP Server via CLI

```bash
loco mcp add-json <name> '<json-config>'
```

Example with GitHub Copilot:
```bash
loco mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer YOUR_TOKEN"}}'
```

### Configuration Format

#### HTTP Server Configuration

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

#### Command Server Configuration

```json
{
  "type": "command",
  "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem"],
  "args": ["/path/to/directory"],
  "env": {
    "GITHUB_TOKEN": "${GITHUB_TOKEN}"
  },
  "cwd": "/optional/working/directory"
}
```

### Manual Configuration

Edit `~/.config/loco/config.json`:

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

## Implementation Details

### Files Modified/Created

1. **src/loco/config.py**
   - Updated `MCPServerConfig` to support both `command` and `http` types
   - Added validation via `model_post_init`
   - Made `mcp_servers` accept dict or MCPServerConfig instances

2. **src/loco/mcp/transport.py**
   - Added `HTTPTransport` class for HTTP/SSE-based MCP communication
   - Requires `aiohttp` dependency

3. **src/loco/mcp/client.py**
   - Added `from_http()` class method for HTTP clients
   - Added `from_config()` class method to create clients from config dicts
   - Supports both command and HTTP configurations

4. **src/loco/mcp/loader.py** (new)
   - Utility functions to load MCP clients from configuration
   - `load_mcp_clients()` - Load all configured MCP servers
   - `load_mcp_client(name)` - Load a specific MCP server

5. **src/loco/cli.py**
   - Updated `add-json` command to validate and support both config types
   - Better error messages and examples

6. **pyproject.toml**
   - Added `mcp-http` optional dependency group with `aiohttp`

7. **examples/mcp/config-with-mcp.json**
   - Updated example config to show both types
   - Added HTTP example

8. **examples/mcp/README.md**
   - Updated documentation with HTTP examples
   - Added installation instructions for HTTP support

### Architecture

```
┌─────────────────────────────────────────┐
│         MCPServerConfig                 │
│  (Pydantic model with validation)       │
│                                         │
│  - type: "command" | "http"            │
│  - command/args/env/cwd (for command)  │
│  - url/headers (for http)              │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│          MCPClient.from_config()        │
│     (Factory method - dispatcher)       │
└─────────────────────────────────────────┘
            │                    │
            ▼                    ▼
┌───────────────────┐  ┌─────────────────┐
│  ProcessTransport │  │  HTTPTransport  │
│  (stdio/pipes)    │  │  (HTTP/SSE)     │
└───────────────────┘  └─────────────────┘
            │                    │
            └────────┬───────────┘
                     ▼
            ┌─────────────────┐
            │    MCPClient    │
            │  (unified API)  │
            └─────────────────┘
```

### HTTPTransport Implementation

The `HTTPTransport` class implements the MCP protocol over HTTP using:
- **POST requests** for sending JSON-RPC messages
- **Server-Sent Events (SSE)** for receiving responses
- **aiohttp** for async HTTP operations

Key features:
- Automatic session management
- Custom headers support (for authentication)
- Graceful error handling
- Async queue-based message receiving

## Installation

For HTTP MCP support, install with:

```bash
pip install aiohttp
# or
pip install 'loco[mcp-http]'
```

## Testing

Run the integration test:

```python
from loco.config import load_config
from loco.mcp.loader import load_mcp_clients

config = load_config()
clients = load_mcp_clients(config)

for name, client in clients.items():
    print(f"Loaded: {name} ({type(client.transport).__name__})")
```

## Future Enhancements

Possible improvements:
1. Add `loco mcp list` command to show configured servers
2. Add `loco mcp test <name>` to test connectivity
3. Auto-discover and register MCP server tools on startup
4. Support WebSocket transport in addition to SSE
5. Add authentication methods (OAuth, API keys, etc.)
6. Support for MCP server discovery/registry

## Compatibility

- Backward compatible with existing command-based configurations
- `type` field defaults to `"command"` if not specified
- Existing configs will continue to work without modification
