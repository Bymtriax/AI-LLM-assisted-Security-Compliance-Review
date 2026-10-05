"""Serve stateless chat requests to the Agent."""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent import AgentService
from api import Message


class ChatMessage(BaseModel):
    """A conversation or retrieval message shown to the user."""

    model_config = ConfigDict(extra="forbid", strict=True)

    role: Literal["user", "assistant", "system"]
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, content: str) -> str:
        if not content.strip():
            raise ValueError("Message content must be non-empty text.")
        return content


class ChatRequest(BaseModel):
    """The displayed message history, ending with the latest user message."""

    model_config = ConfigDict(extra="forbid", strict=True)

    messages: list[ChatMessage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_latest_message(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The latest message must be from the user.")
        return self


class ChatResponse(BaseModel):
    """New messages to append in their display order."""

    messages: list[ChatMessage]


def create_app(*, allowed_origins: list[str] | None = None) -> FastAPI:
    """Create the HTTP app with optional allowed browser origins."""
    if allowed_origins is None:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        allowed_origins = [
            origin.strip()
            for origin in os.getenv("WEB_API_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]

    app = FastAPI(title="Security Compliance Agent API")
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["POST"],
            allow_headers=["Content-Type"],
        )

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        messages = [
            Message(role=message.role, content=message.content)
            for message in request.messages
            if message.role in {"user", "assistant"}
        ]
        replies = AgentService().respond(messages)
        response_messages = [
            ChatMessage(role=message.role, content=message.content)
            for message in replies
        ]
        return ChatResponse(messages=response_messages)

    return app


app = create_app()
