"""Call the SiliconFlow language model."""

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from api.models import Message


API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V4-Flash"


def generate_text(text: str) -> str:
    """Send text to the model and return its reply."""
    return generate_messages([Message(role="user", content=text)])


def generate_messages(messages: list[Message]) -> str:
    """Send chat messages to the model and return its reply."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

    request = Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['SILICONFLOW_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["choices"][0]["message"]["content"]
