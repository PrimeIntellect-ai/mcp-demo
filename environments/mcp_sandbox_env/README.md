# MCP Sandbox Environment

A general-purpose environment for running any MCP (Model Context Protocol) server inside Prime sandboxes with exposed ports

## Installation

```bash
uv run vf-install mcp_sandbox_env
```

## Quick Start

### Single MCP Server

The environment includes three ready-to-use examples:

```bash
# Browserbase - Browser automation
export BROWSERBASE_API_KEY="your-key"
export BROWSERBASE_PROJECT_ID="your-project"
export OPENAI_API_KEY="your-key"
uv run vf-eval -s mcp_sandbox_env -m gpt-4.1 -n 1 -a '{"server_config": ["BROWSERBASE_CONFIG"]}'

# MongoDB - Database operations
uv run vf-eval -s mcp_sandbox_env -m gpt-4.1 -n 1 -a '{"server_config": ["MONGODB_CONFIG"]}'

# Box - File storage operations
export BOX_CLIENT_ID="your-id"
export BOX_CLIENT_SECRET="your-secret"
export BOX_SUBJECT_ID="your-user-id"
uv run vf-eval -s mcp_sandbox_env -m gpt-4.1 -n 1 -a '{"server_config": ["BOX_CONFIG"]}'
```

### Multiple MCP Servers

Combine multiple MCP servers in a single environment with a custom dataset:

```bash
# Using multiple MCPs with a custom dataset
uv run vf-eval -s mcp_sandbox_env -m gpt-4.1 -n 1 -a '{
  "server_config": ["BROWSERBASE_CONFIG", "MONGODB_CONFIG"],
  "dataset": {
    "question": ["Browse HackerNews and save top stories to MongoDB"],
    "answer": ["Successfully saved stories"]
  }
}'
```

## Tool Filtering

You can filter which tools to expose from an MCP server using the `allowed_tools` parameter. This is useful when an MCP server provides many tools but you only need a subset:

```bash
export BROWSERBASE_API_KEY="your-key"
export BROWSERBASE_PROJECT_ID="your-project"
uv run vf-eval -s mcp_sandbox_env -m gpt-4.1 -n 1 -a '{"server_config": ["BROWSERBASE_CONFIG_FILTERED"]}'
```

See `examples/browserbase_config_filtered.py` for an example of how to configure tool filtering.

## Creating Your Own MCP Config

Create a config dictionary and register it with CONFIGS:

```python
import os
from datasets import Dataset
from examples import CONFIGS
from mcp_sandbox_env import load_environment

# Define your custom config
MY_SERVER_CONFIG = {
    # Basic server info
    "name": "my-server",
    "docker_image": "node:22-slim",
    "server_start_cmd": "npx -y my-mcp-server --port 3000",

    # Environment variables
    "server_env": {
        "MY_API_KEY": os.getenv("MY_API_KEY"),
    },

    # Setup commands (install dependencies, clone repos, etc.)
    "pre_install_cmds": [
        "apt-get update && apt-get install -y git",
        "git clone https://github.com/user/my-mcp-server.git",
    ],

    # MCP connection details
    "mcp_port": 3000,
    "mcp_path": "/mcp",

    # Optional: Filter tools by name (omit to expose all tools)
    "allowed_tools": [
        "tool_name_1",
        "tool_name_2",
        "tool_name_3",
    ],

    # Dataset for evaluation
    "dataset": {
        "question": ["Task 1: Do something", "Task 2: Another task"],
        "answer": ["Expected result 1", "Expected result 2"],
    },

    # Rubric for scoring
    "rubric": get_rubric,

    # System prompt to instruct the agent
    "system_prompt": "",
}

# Register it in CONFIGS in examples/__init__.py
CONFIGS = {
    # ... other configs ...
    "MY_SERVER_CONFIG": MY_SERVER_CONFIG,
}

# Now use it like any predefined config
env = load_environment(server_config=["MY_SERVER_CONFIG"])

# Or with a custom dataset
custom_dataset = Dataset.from_dict({
    "question": ["Custom task"],
    "answer": ["Custom answer"],
})
env = load_environment(
    server_config=["MY_SERVER_CONFIG", "MONGODB_CONFIG"],
    dataset=custom_dataset
)
```

You can also reference the example configs in `examples/` for more complete examples.
