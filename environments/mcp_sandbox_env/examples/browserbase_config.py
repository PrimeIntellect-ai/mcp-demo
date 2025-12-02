import os

import verifiers as vf

SYSTEM_PROMPT = """You are a web automation agent with access to browser control tools.

Your task is to complete web navigation tasks using the provided tools. You MUST use the browser tools to:
1. Navigate to websites
2. Take screenshots to observe the page
3. Interact with elements (click, type, scroll, etc.)

Always start by navigating to a URL, then take a screenshot to see what's on the page.
Use tool calls to complete the task - do not just describe what to do.
Continue using tools until the task is fully complete."""


def get_rubric() -> vf.Rubric:
    rubric = vf.JudgeRubric(judge_model="gpt-4.1-mini")

    async def judge_reward(judge, prompt, completion, answer, state):
        jr = await judge(prompt, completion, answer, state)
        return 1.0 if "yes" in jr.lower() else 0.0

    rubric.add_reward_func(judge_reward, weight=1.0)
    return rubric


BROWSERBASE_CONFIG = {
    "name": "browserbase",
    "docker_image": "node:22-slim",
    "server_start_cmd": "cd mcp-server-browserbase && node cli.js --port 3000",
    "server_env": {
        "BROWSERBASE_API_KEY": os.getenv("BROWSERBASE_API_KEY"),
        "BROWSERBASE_PROJECT_ID": os.getenv("BROWSERBASE_PROJECT_ID"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    },
    "pre_install_cmds": [
        "apt-get update && apt-get install -y git && npm install -g pnpm",
        "git clone https://github.com/browserbase/mcp-server-browserbase.git",
        "cd mcp-server-browserbase && pnpm install && pnpm run build",
    ],
    "mcp_port": 3000,
    "mcp_path": "/mcp",
    "dataset": {
        "question": ["Go to HackerNews and get the title of the second story."],
        "answer": ["The Collapse of the Econ PhD Job Market"],
    },
    "rubric": get_rubric,
    "system_prompt": SYSTEM_PROMPT,
}
