"""MCP Client implementation for connecting to external MCP servers."""

import asyncio
import uuid
from typing import Any
from loco.mcp.protocol import (
    MCP_VERSION,
    MCPRequest,
    MCPResponse,
    InitializeParams,
    CallToolParams,
    ToolInfo,
)
from loco.mcp.transport import MCPTransport, ProcessTransport
from loco.tools.base import Tool


class MCPClientTool(Tool):
    """Wrapper to expose an MCP server's tool as a loco Tool."""

    def __init__(self, tool_info: ToolInfo, client: "MCPClient"):
        self._tool_info = tool_info
        self._client = client

    @property
    def name(self) -> str:
        return self._tool_info.name

    @property
    def description(self) -> str:
        return self._tool_info.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._tool_info.inputSchema

    def execute(self, **kwargs: Any) -> str:
        """Execute the tool via the MCP client."""
        # Run the async call synchronously
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, we need to handle this differently
            # For now, raise an error
            raise RuntimeError(
                "Cannot execute MCP tool synchronously from async context. "
                "Use await client.call_tool() instead."
            )
        
        return loop.run_until_complete(self._client.call_tool(self.name, kwargs))


class MCPClient:
    """MCP client for connecting to external MCP servers."""

    def __init__(
        self,
        transport: MCPTransport,
        client_name: str = "loco",
        client_version: str = "0.1.0",
    ):
        self.transport = transport
        self.client_name = client_name
        self.client_version = client_version
        self._initialized = False
        self._request_id = 0
        self._pending_requests: dict[str | int, asyncio.Future] = {}
        self._tools: dict[str, ToolInfo] = {}
        self._receive_task: asyncio.Task | None = None

    def _next_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    async def _send_request(
        self, 
        method: str, 
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a request and wait for response."""
        request_id = self._next_id()
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self._pending_requests[request_id] = future

        request = MCPRequest(
            id=request_id,
            method=method,
            params=params,
        )

        await self.transport.send(request.model_dump())

        try:
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=30.0)
            
            if "error" in response:
                error = response["error"]
                raise RuntimeError(
                    f"MCP Error {error.get('code')}: {error.get('message')}"
                )
            
            return response.get("result", {})
        
        finally:
            self._pending_requests.pop(request_id, None)

    async def _receive_loop(self) -> None:
        """Receive and handle responses."""
        try:
            async for message in self.transport.receive():
                # Check if it's a response to a pending request
                if "id" in message:
                    request_id = message["id"]
                    future = self._pending_requests.get(request_id)
                    
                    if future and not future.done():
                        future.set_result(message)
                # Could also handle notifications here
        
        except Exception as e:
            # Fail all pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(e)

    async def initialize(self) -> dict[str, Any]:
        """Initialize the connection with the MCP server."""
        if self._initialized:
            return {}
        
        # Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())

        params = InitializeParams(
            protocolVersion=MCP_VERSION,
            capabilities={
                "tools": {},  # We support receiving tools
            },
            clientInfo={
                "name": self.client_name,
                "version": self.client_version,
            },
        )

        result = await self._send_request("initialize", params.model_dump())
        self._initialized = True

        # Send initialized notification
        await self.transport.send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        return result

    async def list_tools(self) -> list[ToolInfo]:
        """List available tools from the MCP server."""
        if not self._initialized:
            await self.initialize()

        result = await self._send_request("tools/list")
        tools_data = result.get("tools", [])
        
        tools = []
        for tool_data in tools_data:
            tool_info = ToolInfo(**tool_data)
            tools.append(tool_info)
            self._tools[tool_info.name] = tool_info
        
        return tools

    async def call_tool(
        self, 
        name: str, 
        arguments: dict[str, Any] | None = None
    ) -> str:
        """Call a tool on the MCP server."""
        if not self._initialized:
            await self.initialize()

        params = CallToolParams(name=name, arguments=arguments)
        result = await self._send_request("tools/call", params.model_dump())
        
        # Extract text content from result
        content = result.get("content", [])
        texts = []
        
        for item in content:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
        
        return "\n".join(texts)

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool wrapper for use in loco's tool registry."""
        tool_info = self._tools.get(name)
        if tool_info is None:
            return None
        
        return MCPClientTool(tool_info, self)

    async def close(self) -> None:
        """Close the client connection."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        await self.transport.close()

    @classmethod
    def from_command(
        cls,
        command: list[str],
        cwd: str | None = None,
        client_name: str = "loco",
        client_version: str = "0.1.0",
    ) -> "MCPClient":
        """Create an MCP client that spawns a server process."""
        transport = ProcessTransport(command, cwd)
        return cls(transport, client_name, client_version)

    @classmethod
    def from_http(
        cls,
        url: str,
        headers: dict[str, str] | None = None,
        client_name: str = "loco",
        client_version: str = "0.1.0",
    ) -> "MCPClient":
        """Create an MCP client that connects to an HTTP-based MCP server."""
        from loco.mcp.transport import HTTPTransport
        transport = HTTPTransport(url, headers)
        return cls(transport, client_name, client_version)

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        client_name: str = "loco",
        client_version: str = "0.1.0",
    ) -> "MCPClient":
        """Create an MCP client from a configuration dictionary.
        
        Supports both command-based and HTTP-based configurations.
        """
        config_type = config.get("type", "command")
        
        if config_type == "http":
            url = config.get("url")
            if not url:
                raise ValueError("HTTP MCP server config must have 'url' field")
            headers = config.get("headers", {})
            return cls.from_http(url, headers, client_name, client_version)
        else:  # command
            command = config.get("command")
            if not command:
                raise ValueError("Command-based MCP server config must have 'command' field")
            args = config.get("args", [])
            cwd = config.get("cwd")
            
            # Combine command and args
            full_command = command + args if args else command
            return cls.from_command(full_command, cwd, client_name, client_version)
