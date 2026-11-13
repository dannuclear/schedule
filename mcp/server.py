import os
from mcp.server import MCPServer

from teachers import register_tools

HOST = os.environ.get("MCP_HOST", "0.0.0.0")  # слушать на всех интерфейсах машины
PORT = int(os.environ.get("MCP_PORT", "8200"))

server = MCPServer("school-schedule", version="0.1.0")
register_tools(server)

if __name__ == "__main__":
    server.run(transport="streamable-http", host=HOST, port=PORT)