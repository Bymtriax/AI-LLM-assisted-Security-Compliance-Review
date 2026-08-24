"""Data types used by external API wrappers."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Message:
    """One message sent to a chat-completions API."""

    role: Literal["system", "user", "assistant"]
    content: str
