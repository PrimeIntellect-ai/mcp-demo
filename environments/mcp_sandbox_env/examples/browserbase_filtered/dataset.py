"""Dataset loader for Online-Mind2Web benchmark.

https://huggingface.co/datasets/osunlp/Online-Mind2Web
"""

from datasets import load_dataset


def load_mind2web_dataset():
    dataset = load_dataset("osunlp/Online-Mind2Web", split="test")

    questions = []
    infos = []

    for item in dataset:
        questions.append(item["confirmed_task"])
        infos.append(
            {
                "task_id": item["task_id"],
                "website": item["website"],
                "reference_length": item["reference_length"],
            }
        )

    return {
        "question": questions,
        "answer": [""] * len(questions),  # No ground truth answers available
        "info": infos,
    }
