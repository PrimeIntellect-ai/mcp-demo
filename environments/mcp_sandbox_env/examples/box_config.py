import os

import verifiers as vf

SYSTEM_PROMPT = """You are a file management assistant with access to Box cloud storage tools.

Your task is to complete file operations using the provided tools. You MUST use the Box tools to:
1. Search for files and folders
2. Upload and download files
3. Manage file metadata and permissions

Use tool calls to complete the file operations - do not just describe what to do.
Continue using tools until the task is fully complete."""


def get_rubric() -> vf.Rubric:
    rubric = vf.JudgeRubric(judge_model="gpt-4.1-mini")

    async def judge_reward(judge, prompt, completion, answer, state):
        jr = await judge(prompt, completion, answer, state)
        return 1.0 if "yes" in jr.lower() else 0.0

    rubric.add_reward_func(judge_reward, weight=1.0)
    return rubric


BOX_CONFIG = {
    "name": "box",
    "docker_image": "astral/uv:python3.14-alpine",
    "server_start_cmd": "cd mcp-server-box && uv run src/mcp_server_box.py --transport streamable-http --host 0.0.0.0 --port 3002 --box-auth ccg --no-mcp-server-auth",
    "server_env": {
        "BOX_CLIENT_ID": os.getenv("BOX_CLIENT_ID"),
        "BOX_CLIENT_SECRET": os.getenv("BOX_CLIENT_SECRET"),
        "BOX_SUBJECT_TYPE": os.getenv("BOX_SUBJECT_TYPE", "user"),
        "BOX_SUBJECT_ID": os.getenv("BOX_SUBJECT_ID"),
    },
    "pre_install_cmds": [
        "git clone https://github.com/box-community/mcp-server-box.git",
        "cd mcp-server-box && uv sync",
    ],
    "mcp_port": 3002,
    "mcp_path": "/mcp",
    "dataset": {
        "question": [
            "Search for files in Box containing 'project' in their name and list the file IDs and names you find."
        ],
        "answer": ["TODO"],
    },
    "rubric": get_rubric,
    "system_prompt": SYSTEM_PROMPT,
}
