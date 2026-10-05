"""Coordinate one conversation with the language model."""

import json
from typing import Any

from api import Message, generate_messages
from agent.prompts import SYSTEM_MESSAGE
from rag.rag_service import RAGService


class ModelResponseError(ValueError):
    """A model reply that the Agent cannot use, with its original content."""

    def __init__(self, message: str, *, raw_response: object) -> None:
        super().__init__(message)
        self.raw_response = raw_response


class AgentService:
    """Generate a reply from caller-supplied conversation messages."""

    def __init__(self) -> None:
        self._rag = RAGService()

    def respond(self, messages: list[Message]) -> list[Message]:
        """Return new display messages without retaining conversation history."""
        self._validate_messages(messages)
        request_messages = [SYSTEM_MESSAGE, *messages]
        model_output = generate_messages(request_messages)
        return self._process_model_output(model_output, request_messages)

    @staticmethod
    def _validate_messages(messages: list[Message]) -> None:
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list.")
        for message in messages:
            if not isinstance(message, Message):
                raise TypeError("Each message must be a Message.")
            if message.role not in {"user", "assistant"}:
                raise ValueError("Conversation messages must be user or assistant.")
            if not isinstance(message.content, str) or not message.content.strip():
                raise ValueError("Message content must be non-empty text.")
        if messages[-1].role != "user":
            raise ValueError("The latest message must be from the user.")

    def _process_model_output(
        self,
        model_output: str,
        request_messages: list[Message],
    ) -> list[Message]:
        """Return an answer directly or execute one regulation retrieval."""
        result = self._parse_model_output(model_output, phase="initial decision")

        if result.get("type") == "answer":
            return [
                Message(
                    role="assistant",
                    content=self._answer_content(
                        result, model_output, phase="initial decision"
                    ),
                )
            ]

        if result.get("type") != "tool_call":
            raise ModelResponseError(
                "Unknown Agent response type during initial decision.",
                raw_response=model_output,
            )
        if result.get("tool") != "retrieve_regulations":
            raise ModelResponseError(
                "Unknown Agent tool during initial decision.",
                raw_response=model_output,
            )
        arguments = result.get("arguments")
        if not isinstance(arguments, dict) or not isinstance(
            arguments.get("text"), str
        ) or not arguments["text"].strip():
            raise ModelResponseError(
                "Invalid regulation search text during initial decision.",
                raw_response=model_output,
            )
        query_text = arguments["text"]

        records = self._rag.retrieve(query_text)
        evidence = "\n\n".join(records) if records else "No matching regulations found."
        evidence_message = Message(
            role="system",
            content=(
                f"Regulation search: {query_text}\n"
                f"Search results:\n{evidence}"
            ),
        )
        final_output = generate_messages([*request_messages, evidence_message])
        final_result = self._parse_model_output(
            final_output, phase="answer after regulation retrieval"
        )

        if final_result.get("type") != "answer":
            raise ModelResponseError(
                "Expected an answer after regulation retrieval.",
                raw_response=final_output,
            )
        return [
            evidence_message,
            Message(
                role="assistant",
                content=self._answer_content(
                    final_result, final_output, phase="answer after regulation retrieval"
                ),
            ),
        ]

    @staticmethod
    def _answer_content(
        result: dict[str, Any], output: str, *, phase: str
    ) -> str:
        content = result.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ModelResponseError(
                f"Model returned empty or non-text answer content during {phase}.",
                raw_response=output,
            )
        return content

    @staticmethod
    def _parse_model_output(output: str, *, phase: str) -> dict[str, Any]:
        """Identify where a malformed model response interrupted the turn."""
        if not isinstance(output, str):
            raise ModelResponseError(
                f"Model returned non-text content during {phase}.",
                raw_response=output,
            )
        if not output.strip():
            raise ModelResponseError(
                f"Model returned empty content during {phase}.",
                raw_response=output,
            )
        try:
            result = json.loads(output)
        except json.JSONDecodeError as error:
            kind = (
                "a Markdown code fence"
                if output.lstrip().startswith("```")
                else "invalid JSON"
            )
            raise ModelResponseError(
                f"Model returned {kind} during {phase} "
                f"({len(output)} characters; parse error at character {error.pos}).",
                raw_response=output,
            ) from error
        if not isinstance(result, dict):
            raise ModelResponseError(
                f"Model returned a non-object JSON value during {phase}.",
                raw_response=output,
            )
        return result
