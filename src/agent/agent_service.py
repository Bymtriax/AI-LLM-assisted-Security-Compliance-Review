"""Coordinate one conversation with the language model."""

import json

from api import Message, generate_messages
from agent.prompts import SYSTEM_MESSAGE
from rag.rag_service import RAGService


class AgentService:
    """Store conversation messages and generate replies."""

    def __init__(self) -> None:
        self._messages: list[Message] = []
        self._rag = RAGService()

    @property
    def messages(self) -> list[Message]:
        """Return a copy of the visible conversation messages."""
        return list(self._messages)

    def respond(self, text: str) -> str:
        """Add one user message and return the model reply."""
        self._messages.append(Message(role="user", content=text))
        model_output = generate_messages([SYSTEM_MESSAGE, *self._messages])
        answer = self._process_model_output(model_output)

        self._messages.append(Message(role="assistant", content=answer))
        return answer

    def _process_model_output(self, model_output: str) -> str:
        """Return an answer directly or execute one regulation retrieval."""
        result = json.loads(model_output)

        if result["type"] == "answer":
            return result["content"]

        if result["type"] != "tool_call":
            raise ValueError("Unknown Agent response type.")
        if result["tool"] != "retrieve_regulations":
            raise ValueError("Unknown Agent tool.")

        records = self._rag.retrieve(result["arguments"]["text"])
        query_text = result["arguments"]["text"]
        evidence = "\n\n".join(records) if records else "No matching regulations found."
        evidence_message = Message(
            role="system",
            content=(
                f"Regulation search: {query_text}\n"
                f"Search results:\n{evidence}"
            ),
        )
        self._messages.append(evidence_message)
        final_output = generate_messages(
            [SYSTEM_MESSAGE, *self._messages]
        )
        final_result = json.loads(final_output)

        if final_result["type"] != "answer":
            raise ValueError("Expected an answer after regulation retrieval.")
        return final_result["content"]
