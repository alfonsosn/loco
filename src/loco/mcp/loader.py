"""Utilities for loading MCP clients from configuration."""

from typing import Any
from loco.mcp.client import MCPClient
from loco.config import Config


def load_mcp_clients(config: Config) -> dict[str, MCPClient]:
    """Load all MCP clients from configuration.
    
    Returns a dictionary mapping server names to MCPClient instances.
    """
    clients: dict[str, MCPClient] = {}
    
    for name, server_config in config.mcp_servers.items():
        try:
            # Convert to dict if it's a Pydantic model
            if not isinstance(server_config, dict):
                config_dict = server_config.model_dump(exclude_none=True)
            else:
                config_dict = server_config
            
            client = MCPClient.from_config(config_dict)
            clients[name] = client
        except Exception as e:
            import sys
            sys.stderr.write(f"Warning: Failed to load MCP server '{name}': {e}\n")
            sys.stderr.flush()
    
    return clients


def load_mcp_client(config: Config, name: str) -> MCPClient | None:
    """Load a specific MCP client by name.
    
    Returns None if the server is not configured or fails to load.
    """
    server_config = config.mcp_servers.get(name)
    if server_config is None:
        return None
    
    try:
        # Convert to dict if it's a Pydantic model
        if not isinstance(server_config, dict):
            config_dict = server_config.model_dump(exclude_none=True)
        else:
            config_dict = server_config
        
        return MCPClient.from_config(config_dict)
    except Exception as e:
        import sys
        sys.stderr.write(f"Warning: Failed to load MCP server '{name}': {e}\n")
        sys.stderr.flush()
        return None
