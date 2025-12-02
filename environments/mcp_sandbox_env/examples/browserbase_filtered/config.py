import os

from .dataset import load_mind2web_dataset
from .rubric import get_rubric

SYSTEM_PROMPT = """You are a web automation agent with access to browser control tools.

Your task is to complete web navigation tasks using the provided tools. You MUST use the browser tools to:
1. Navigate to websites
2. Take screenshots to observe the page
3. Interact with elements (click, type, scroll, etc.)

Always start by creating a session, then navigating to a URL, then taking a screenshot to see what's on the page.
Use tool calls to complete the task - do not just describe what to do.
Continue using tools until the task is fully complete."""


BROWSERBASE_CONFIG_FILTERED = {
    "name": "browserbase-filtered",
    "docker_image": "node:22-slim",
    "server_start_cmd": "cd mcp-server-browserbase && node cli.js --port 3000",
    "server_env": {
        "BROWSERBASE_API_KEY": os.getenv("BROWSERBASE_API_KEY"),
        "BROWSERBASE_PROJECT_ID": os.getenv("BROWSERBASE_PROJECT_ID"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    },
    "pre_install_cmds": [
        "apt-get update && apt-get install -y git && npm install -g pnpm",
        "git clone https://github.com/kcoopermiller/mcp-server-browserbase.git",
        "cd mcp-server-browserbase && pnpm install && pnpm run build",
    ],
    "mcp_port": 3000,
    "mcp_path": "/mcp",
    "allowed_tools": [
        "browserbase_session_create",
        "browserbase_session_close",
        "browserbase_stagehand_navigate",
        "browserbase_stagehand_cu_screenshot",
        "browserbase_stagehand_cu_click",
        "browserbase_stagehand_cu_double_click",
        "browserbase_stagehand_cu_scroll",
        "browserbase_stagehand_cu_type",
        "browserbase_stagehand_cu_wait",
        "browserbase_stagehand_cu_move",
        "browserbase_stagehand_cu_keypress",
        "browserbase_stagehand_cu_drag",
    ],
    "dataset": load_mind2web_dataset,
    "rubric": get_rubric,
    "system_prompt": SYSTEM_PROMPT,
}
