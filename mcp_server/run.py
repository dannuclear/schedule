import os

import uvicorn

from .server import app

HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8200"))


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
