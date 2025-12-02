import asyncio
import logging
from typing import Dict, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent, Tool


class MCPServerConnection:
    """HTTP-only MCP connection for sandbox servers."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]], logger: logging.Logger):
        self.url = url
        self.headers = headers or {}
        self.logger = logger
        self.session: Optional[ClientSession] = None
        self.tools: Dict[str, Tool] = {}

        self._connection_task: Optional[asyncio.Task] = None
        self._ready = asyncio.Event()
        self._error: Optional[Exception] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self):
        """Connect to the MCP server via HTTP and retrieve tools."""
        self.loop = asyncio.get_running_loop()
        self._connection_task = asyncio.create_task(self._get_connection())

        await self._ready.wait()

        if self._error:
            raise self._error

        return self.tools

    async def _get_connection(self):
        try:
            async with streamablehttp_client(
                self.url,
                headers=self.headers,
            ) as (read, write, _get_session_id):
                async with ClientSession(read, write) as session:
                    self.session = session

                    await session.initialize()

                    tools_response = await session.list_tools()

                    for tool in tools_response.tools:
                        self.tools[tool.name] = tool

                    self._ready.set()

                    # Keep connection alive
                    while True:
                        await asyncio.sleep(1)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._error = e
            self._ready.set()
        finally:
            self.session = None
            self.tools = {}

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool on the MCP server."""
        assert self.session is not None, "MCP server not connected"
        assert self.loop is not None, "Connection loop not initialized"

        fut = asyncio.run_coroutine_threadsafe(self.session.call_tool(tool_name, arguments=arguments), self.loop)
        result = await asyncio.wrap_future(fut)

        if result.content:
            text_parts = []
            for content_item in result.content:
                if hasattr(content_item, "text"):
                    assert isinstance(content_item, TextContent)
                    text_parts.append(content_item.text)
                elif hasattr(content_item, "type") and content_item.type == "text":
                    text_parts.append(getattr(content_item, "text", str(content_item)))
                else:
                    text_parts.append(str(content_item))

            return "\n".join(text_parts)

        return "No result returned from tool"

    async def disconnect(self):
        """Disconnect from the MCP server."""
        assert self._connection_task is not None
        self._connection_task.cancel()
        try:
            await self._connection_task
        except asyncio.CancelledError:
            pass
        self.logger.info("MCP server connection terminated")
