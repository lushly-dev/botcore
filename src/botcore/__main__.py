"""Entry point for `python -m botcore` — starts the MCP server."""

from botcore.server import create_mcp_server

server = create_mcp_server("botcore", version="0.2.0")
server.run(transport="stdio")
