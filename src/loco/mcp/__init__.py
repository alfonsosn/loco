"""Model Context Protocol (MCP) integration for loco."""

from loco.mcp.server import MCPServer
from loco.mcp.client import MCPClient
from loco.mcp.transport import StdioTransport, SSETransport, HTTPTransport
from loco.mcp.loader import load_mcp_clients, load_mcp_client

__all__ = [
    "MCPServer",
    "MCPClient",
    "StdioTransport",
    "SSETransport",
    "HTTPTransport",
    "load_mcp_clients",
    "load_mcp_client",
]
