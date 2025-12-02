"""Template MCP Server Configuration

Use this template to create your own MCP server configuration.
Copy this file and modify it for your specific MCP server.
"""

import os

import verifiers as vf


def get_rubric() -> vf.Rubric:
    """Create and return the rubric for this environment."""
    rubric = vf.JudgeRubric(judge_model="gpt-4.1-mini")

    async def judge_reward(judge, prompt, completion, answer, state):
        jr = await judge(prompt, completion, answer, state)
        return 1.0 if "yes" in jr.lower() else 0.0

    rubric.add_reward_func(judge_reward, weight=1.0)
    return rubric


# Replace with your server name
MY_SERVER_CONFIG = {
    # Unique name for your MCP server
    "name": "my-server",
    # Docker image to use for the sandbox
    # Common options: "node:22-slim", "python:3.11-slim"
    "docker_image": "node:22-slim",
    # Command to start your MCP server
    # Should include the port and any necessary flags
    "server_start_cmd": "npx -y my-mcp-server --port 3000",
    # Environment variables needed by your server
    "server_env": {
        "MY_API_KEY": os.getenv("MY_API_KEY"),
        # Add more environment variables as needed
    },
    # Commands to run before starting the MCP server
    # Install dependencies, clone repos, set up databases, etc.
    "pre_install_cmds": [
        "apt-get update && apt-get install -y git",
        # "git clone https://github.com/user/my-mcp-server.git",
        # "cd my-mcp-server && npm install",
    ],
    # Port where your MCP server will listen
    "mcp_port": 3000,
    # Path for MCP endpoint (usually "/mcp")
    "mcp_path": "/mcp",
    # Allowed tools to expose (omit to expose all tools)
    "allowed_tools": [
        "tool_name_1",
        "tool_name_2",
        "tool_name_3",
    ],
    # Dataset for evaluation
    # questions: list of tasks for the agent to complete
    # answers: list of expected results (used for grading)
    "dataset": {
        "question": [
            "Task 1: Use the MCP server to...",
            "Task 2: Another task...",
        ],
        "answer": [
            "Expected result for task 1",
            "Expected result for task 2",
        ],
    },
    # Rubric for evaluation
    "rubric": get_rubric,
    # System prompt to instruct the agent to use tools
    "system_prompt": "",
}
