"""Simple interfaces for external services used by the project."""

from api.llm_api import generate_messages, generate_text
from api.models import Message


__all__ = ["Message", "generate_messages", "generate_text"]
