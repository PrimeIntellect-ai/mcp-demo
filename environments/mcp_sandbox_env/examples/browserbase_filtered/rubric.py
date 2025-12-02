"""Rubric implementation for Online-Mind2Web evaluation.

1. Key Point Identification: Identify key points required for task completion
2. Key Screenshot Identification: Score screenshot relevance (1-5), keep if ≥ 3
3. Outcome Judgment: Binary success/failure using key points + key screenshots + actions

https://tiancixue.notion.site/An-Illusion-of-Progress-Assessing-the-Current-State-of-Web-Agents-1ac6cd2b9aac80719cd6f68374aaf4b4
"""

from typing import Literal

import verifiers as vf
from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class KeyPointsIdentification(BaseModel):
    key_points: list[str] = Field(
        description="3-5 specific key points that must be accomplished for successful task completion"
    )


class ScreenshotRelevance(BaseModel):
    relevance_score: Literal[1, 2, 3, 4, 5] = Field(
        description="Relevance score: 5=highly relevant (critical steps), 4=very relevant, 3=moderately relevant, 2=slightly relevant, 1=not relevant"
    )
    reason: str = Field(description="Brief explanation for the relevance score")


class OutcomeJudgment(BaseModel):
    success: bool = Field(description="True if task was fully completed, False otherwise")
    analysis: str = Field(description="Detailed reasoning for the judgment")
    completed_key_points: list[str] = Field(description="List of key points that were successfully completed")
    missing_key_points: list[str] = Field(description="List of key points that were not completed")


def extract_screenshots_for_vision(completion):
    screenshots = []

    print(f"Completion: {completion}")

    for msg in completion:
        if msg.get("role") == "tool":
            content = msg.get("content", [])
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image" and "data" in part:
                    screenshots.append(part)

    return screenshots


def get_rubric() -> vf.Rubric:
    """Create Online-Mind2Web evaluation rubric.

    Uses a three-step LLM-as-a-Judge methodology with vision capabilities:
    1. Key Point Identification (text-only)
    2. Screenshot Relevance Scoring (vision + structured outputs)
    3. Outcome Judgment (vision + text + structured outputs)

    Note: Requires a vision-capable model (gpt-4o-mini or better) for screenshot evaluation.
    """
    rubric = vf.Rubric()
    rubric.class_objects = {
        "parser": rubric.parser,
        "judge_client": AsyncOpenAI(),
        "judge_model": "gpt-4o-mini",
    }

    async def task_success_reward(judge_client, judge_model, prompt, completion, answer, state):
        print(f"Completion TASK SUCCESS REWARD: {completion}")

        # Use cached results if available (to avoid redundant LLM calls)
        if "mind2web_evaluation" in state:
            return state["mind2web_evaluation"]["success_score"]

        screenshots = extract_screenshots_for_vision(completion)

        # Get task description from prompt (last user message)
        task_description = prompt[-1]["content"] if isinstance(prompt, list) else str(prompt)

        # Step 1: Key Point Identification
        step1_prompt = f"""Given this web navigation task, identify the key points that must be accomplished for successful completion.

Task: {task_description}

List 3-5 key points that are critical for completing this task. Be specific and concrete."""

        step1_response = await judge_client.beta.chat.completions.parse(
            model=judge_model,
            messages=[{"role": "user", "content": step1_prompt}],
            response_format=KeyPointsIdentification,
            temperature=0.0,
        )
        step1_result = step1_response.choices[0].message.parsed
        key_points = step1_result.key_points

        # Step 2: Screenshot Relevance Scoring
        key_screenshots = []
        screenshot_threshold = 3

        if screenshots:
            for i, screenshot in enumerate(screenshots[:10]):  # Limit to first 10 screenshots to avoid token overflow
                step2_text = f"""Given this web navigation task and a screenshot, rate how relevant this screenshot is to evaluating task completion.

Task: {task_description}
Key Points: {", ".join(key_points)}

Rate the relevance on a scale of 1-5 where:
- 5 = Highly relevant, shows critical task completion steps
- 4 = Very relevant, shows important progress
- 3 = Moderately relevant, shows some task context
- 2 = Slightly relevant
- 1 = Not relevant"""

                message_content = [{"type": "text", "text": step2_text}]

                message_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{screenshot.get('mimeType', 'image/png')};base64,{screenshot['data']}"
                        },
                    }
                )

                step2_response = await judge_client.beta.chat.completions.parse(
                    model=judge_model,
                    messages=[{"role": "user", "content": message_content}],
                    response_format=ScreenshotRelevance,
                    temperature=0.0,
                )
                step2_result = step2_response.choices[0].message.parsed
                relevance_score = step2_result.relevance_score

                if relevance_score >= screenshot_threshold:
                    key_screenshots.append(
                        {
                            "index": i,
                            "screenshot": screenshot,
                            "relevance": relevance_score,
                            "reason": step2_result.reason,
                        }
                    )

        # Step 3: Outcome Judgment
        # Use key points + key screenshots + raw action history (tool calls) for final decision
        step3_system = f"""You are evaluating whether a web navigation task was successfully completed.

**Task Description:**
{task_description}

**Key Points Required for Success:**
{chr(10).join(f"{i + 1}. {kp}" for i, kp in enumerate(key_points))}

**Key Screenshots Identified ({len(key_screenshots)} relevant screenshots):**
{chr(10).join(f"- Screenshot {s['index'] + 1} (relevance: {s['relevance']}/5): {s['reason']}" for s in key_screenshots) if key_screenshots else "No key screenshots identified"}

**Instructions:**
- Review the agent's tool calls and their results in the conversation below
- Determine whether ALL key points were accomplished based on the actions and screenshots
- Be strict: partial completion = failure
- Only mark as success if there is clear evidence that all key points were completed"""

        step3_messages = [
            {"role": "system", "content": step3_system},
        ]
        step3_messages.extend(prompt)
        step3_messages.extend(completion)

        if key_screenshots:
            screenshot_content = [{"type": "text", "text": "Here are the key screenshots for your evaluation:"}]
            # Add top 5 most relevant screenshots
            for screenshot_data in sorted(key_screenshots, key=lambda x: x["relevance"], reverse=True)[:5]:
                screenshot = screenshot_data["screenshot"]
                if isinstance(screenshot, dict) and screenshot.get("type") == "image" and "data" in screenshot:
                    screenshot_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{screenshot.get('mimeType', 'image/png')};base64,{screenshot['data']}"
                            },
                        }
                    )
            step3_messages.append({"role": "user", "content": screenshot_content})

        # Final prompt asking for judgment
        step3_messages.append(
            {"role": "user", "content": "Based on the conversation and screenshots above, provide your evaluation."}
        )

        step3_response = await judge_client.beta.chat.completions.parse(
            model=judge_model,
            messages=step3_messages,
            response_format=OutcomeJudgment,
            temperature=0.0,
        )
        step3_result = step3_response.choices[0].message.parsed

        success = step3_result.success
        success_score = 1.0 if success else 0.0

        # Cache results in state for reuse by other metrics
        state["mind2web_evaluation"] = {
            "key_points": key_points,
            "key_screenshots": key_screenshots,
            "final_judgment": {
                "success": step3_result.success,
                "analysis": step3_result.analysis,
                "completed_key_points": step3_result.completed_key_points,
                "missing_key_points": step3_result.missing_key_points,
            },
            "success_score": success_score,
        }

        return success_score

    def action_count_metric(prompt, completion, answer, state):
        """Informational metric: Count the number of tool calls made."""
        count = 0
        for msg in completion:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                count += len(msg["tool_calls"])
        return float(count)

    def key_screenshots_metric(prompt, completion, answer, state):
        """Informational metric: Count the number of key screenshots identified (relevance ≥ 3)."""
        eval_results = state.get("mind2web_evaluation", {})
        key_screenshots = eval_results.get("key_screenshots", [])
        return float(len(key_screenshots))

    rubric.add_reward_func(task_success_reward, weight=1.0)
    rubric.add_reward_func(action_count_metric, weight=0.0)
    rubric.add_reward_func(key_screenshots_metric, weight=0.0)

    return rubric
