import asyncio
from typing import Any, Dict, List, Optional

import verifiers as vf
from datasets import Dataset
from dotenv import load_dotenv
from examples import CONFIGS
from src.mcp_server_connection import MCPServerConnection
from src.mcp_tool_wrapper import MCPToolWrapper


class SandboxMCPEnv(vf.SandboxEnv):
    """Sandbox-backed MCP environment with support for multiple MCP servers."""

    def __init__(
        self,
        sandbox_name: str = "sandbox-mcp-env",
        docker_image: str = "node:22-slim",
        start_command: str = "tail -f /dev/null",
        mcp_server_configs: Optional[List[Dict[str, Any]]] = None,
        max_turns: int = 10,
        **kwargs: Any,
    ) -> None:
        load_dotenv()
        super().__init__(
            sandbox_name=sandbox_name,
            docker_image=docker_image,
            start_command=start_command,
            max_turns=max_turns,
            **kwargs,
        )

        self.mcp_server_configs = mcp_server_configs or []
        self._server_connections: List[MCPServerConnection] = []
        self._wrapper_tools: List[MCPToolWrapper] = []
        self._exposure_ids: List[str] = []

    async def _start_mcp_server(self, sandbox_id: str, config: Dict[str, Any]) -> None:
        """Start a single MCP server"""
        server_start_cmd = config.get("server_start_cmd", "")
        if not server_start_cmd:
            raise ValueError("server_start_cmd is required to launch MCP server")

        server_name = config.get("name", "unknown")
        self.logger.info(f"Starting MCP server '{server_name}': {server_start_cmd[:80]}...")
        await self.sandbox_client.wait_for_creation(sandbox_id)
        try:
            # TODO: remove this once timeout is supported
            result = await self.sandbox_client.execute_command(
                sandbox_id, server_start_cmd, env=dict(config.get("server_env", {})), timeout=10
            )
            self.logger.info(f"MCP server '{server_name}' background process started (exit={result.exit_code})")
        except Exception as e:
            self.logger.info(f"Timed out starting MCP server '{server_name}': {e}")
            pass

    async def _expose_port(self, sandbox_id: str, config: Dict[str, Any], index: int) -> str:
        """Expose a single MCP server port"""
        mcp_port = config.get("mcp_port", 3000)
        mcp_path = config.get("mcp_path", "/mcp")
        server_name = config.get("name", f"server-{index}")

        await self.sandbox_client.wait_for_creation(sandbox_id)
        exposed_port = await self.sandbox_client.expose(
            sandbox_id, mcp_port, name=f"mcp-server-{server_name}", protocol="HTTP"
        )

        self._exposure_ids.append(exposed_port.exposure_id)
        url = f"{exposed_port.url}{mcp_path}"

        self.logger.info(f"Port {mcp_port} for '{server_name}' exposed at: {url}")
        return url

    async def _connect_mcp(self, url: str, config: Dict[str, Any]) -> List[MCPToolWrapper]:
        """Connect to a single MCP server via the exposed port."""
        server_name = config.get("name", "unknown")
        self.logger.info(f"Connecting to MCP server '{server_name}' at {url}")

        connection = MCPServerConnection(url, None, self.logger)
        tools = await connection.connect()

        # Get tool filter from config
        allowed_tools = config.get("allowed_tools", None)

        wrappers: List[MCPToolWrapper] = []
        for tool_name, tool in tools.items():
            if allowed_tools is not None and tool_name not in allowed_tools:
                self.logger.debug(f"Filtering out tool '{tool_name}' from '{server_name}'")
                continue

            wrapper = MCPToolWrapper(tool, connection)
            wrappers.append(wrapper)
        self._server_connections.append(connection)

        self.logger.info(f"Connected to '{server_name}' - {len(wrappers)}/{len(tools)} tools available")
        return wrappers

    async def setup_state(self, state: vf.State, **kwargs: Any) -> vf.State:
        state = await super().setup_state(state, **kwargs)
        sandbox_id: str = state["sandbox_id"]

        if not self.mcp_server_configs:
            self.logger.warning("No MCP server configs provided - running without MCP tools")
            return state

        # Expose all ports first
        exposed_urls = []
        for idx, config in enumerate(self.mcp_server_configs):
            url = await self._expose_port(sandbox_id, config, idx)
            exposed_urls.append((url, config))

        # Wait once for cert issuance after all ports are exposed
        # TODO: remove this once cert issuance stuff is fixed
        self.logger.info(f"All {len(self.mcp_server_configs)} MCP servers started, waiting 180s for cert issuance...")
        await asyncio.sleep(180)

        # Process each MCP server config
        for idx, config in enumerate(self.mcp_server_configs):
            server_name = config.get("name", f"server-{idx}")
            self.logger.info(f"Setting up MCP server {idx + 1}/{len(self.mcp_server_configs)}: {server_name}")

            # Run pre-install commands for this server
            pre_install_cmds = config.get("pre_install_cmds", [])
            for cmd in pre_install_cmds:
                response = await self.bash(cmd, sandbox_id)
                self.logger.info(f"[{server_name}] Pre-install command completed: {response[:100]}")

            # Start the MCP server
            await self._start_mcp_server(sandbox_id, config)

        # Now connect to each server
        all_wrappers = []
        for url, config in exposed_urls:
            wrappers = await self._connect_mcp(url, config)
            all_wrappers.extend(wrappers)

        self._wrapper_tools = all_wrappers

        # Register all wrappers explicitly to preserve their MCP-provided schemas
        existing_tools = list(self.tools)
        existing_oai_tools = list(self.oai_tools or [])
        existing_tool_map = dict(self.tool_map)
        for wrapper in self._wrapper_tools:
            existing_tools.append(wrapper)
            existing_oai_tools.append(wrapper.to_oai_tool())
            existing_tool_map[getattr(wrapper, "__name__", wrapper.__class__.__name__)] = wrapper
        self.tools = existing_tools
        self.oai_tools = existing_oai_tools
        self.tool_map = existing_tool_map
        state["info"]["oai_tools"] = self.oai_tools

        # Log all registered MCP tools
        tool_names = [getattr(w, "__name__", w.__class__.__name__) for w in self._wrapper_tools]
        self.logger.info(
            f"Registered {len(self._wrapper_tools)} total MCP tools from {len(self.mcp_server_configs)} servers: {tool_names}"
        )

        return state

    async def is_completed(self, messages: vf.Messages, state: vf.State, **kwargs: Any) -> bool:
        completed = await vf.StatefulToolEnv.is_completed(self, messages, state, **kwargs)
        if completed:
            sandbox_id = state["sandbox_id"]

            # Disconnect from all MCP servers
            for connection in self._server_connections:
                try:
                    await connection.disconnect()
                    self.logger.info("MCP server connection closed")
                except Exception as e:
                    self.logger.error(f"Failed to disconnect from MCP server: {e}")
            self._server_connections = []

            # Unexpose all ports
            for exposure_id in self._exposure_ids:
                try:
                    await self.sandbox_client.unexpose(sandbox_id, exposure_id)
                    self.logger.info(f"Port unexposed: {exposure_id}")
                except Exception as e:
                    self.logger.error(f"Failed to unexpose port: {e}")
            self._exposure_ids = []

            await self.sandbox_client.delete(sandbox_id)
        return completed


def load_environment(
    server_config: List[str],
    dataset=None,
    **kwargs,
) -> vf.Environment:
    """Load an MCP sandbox environment with one or more MCP servers."""
    if not server_config:
        raise ValueError("server_config is required and must contain at least one MCP server configuration")

    mcp_server_configs = []
    docker_image = "node:22-slim"
    rubric = None
    system_prompt = None

    for idx, config_name in enumerate(server_config):
        if config_name not in CONFIGS:
            raise ValueError(f"Unknown config '{config_name}'. Available configs: {list(CONFIGS.keys())}")

        loaded_config = CONFIGS[config_name]
        mcp_server_configs.append(
            {
                "name": loaded_config.get("name", config_name),
                "server_start_cmd": loaded_config["server_start_cmd"],
                "server_env": loaded_config["server_env"],
                "pre_install_cmds": loaded_config["pre_install_cmds"],
                "mcp_port": loaded_config.get("mcp_port", 3000 + idx),
                "mcp_path": loaded_config.get("mcp_path", "/mcp"),
                "allowed_tools": loaded_config.get("allowed_tools", None),
            }
        )

        # Use first config's docker image, dataset, rubric, and system_prompt if not provided
        if idx == 0:
            docker_image = loaded_config.get("docker_image", docker_image)
            system_prompt = loaded_config.get("system_prompt")

            dataset_data = loaded_config.get("dataset")
            if callable(dataset_data):
                dataset_data = dataset_data()
            dataset = dataset or Dataset.from_dict(dataset_data)

            rubric_func = loaded_config.get("rubric")
            if rubric_func is None:
                raise ValueError(f"Config '{config_name}' must provide a 'rubric' field")
            rubric = rubric_func()

    env = SandboxMCPEnv(
        dataset=dataset,
        rubric=rubric,
        docker_image=docker_image,
        mcp_server_configs=mcp_server_configs,
        system_prompt=system_prompt,
        message_type="chat",
        **kwargs,
    )
    env.remove_tool(env.bash)

    return env
