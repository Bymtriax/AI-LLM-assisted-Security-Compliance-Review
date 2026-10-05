# Module Interfaces

Direction: interface provider → interface consumer.

Interfaces marked **Planned** are not implemented; Level 2 workflows and `TBD` outputs remain undecided. `file_path: Path` refers to a server-local uploaded file (`pathlib.Path`).

## Corpus Builder (Vector Store) → RAG

| Interface | Description |
| --- | --- |
| `vector_store.query_vectors(vector: list[float], top_k: int = 3) -> list[CorpusRecord]` | RAG queries the Corpus Builder's vector store for regulation records ordered by similarity. |

Each returned `CorpusRecord` has three fields:

- `id: str`: the unique record identifier.
- `text: str`: the retrieval text, including section, parent section titles, and regulation content for S17 records.
- `metadata: Mapping[str, str | int | float | bool]`: an immutable, flat mapping containing source and traceability information.

Schematic example shown as JSON; the actual return value is a Python `CorpusRecord` object:

```json
{
  "id": "example-record-01",
  "text": "Section: example-section\nParent sections: Example chapter\nText: Example regulation content.",
  "metadata": {
    "document": "S17",
    "version": "8.2",
    "language": "en",
    "section": "example-section",
    "parent_titles": "Example chapter",
    "source_file": "data/raw/standards/en/S17_EN_v8.2_2025-04.pdf",
    "pdf_page_start": 1,
    "printed_page_start": ""
  }
}
```

All metadata fields shown are required; `printed_page_start` may be empty. Additional fields may include `parent_chunk_id`, `part_number`, `part_count`, `split_method`, `word_count`, and `text_sha256`.

## RAG → Agent

| Interface | Description |
| --- | --- |
| `RAGService.retrieve(question_text: str) -> list[str]` | Agent requests matching regulation texts from RAG, ordered by relevance. |
| `RAGService.process_file(file_path: Path) -> TBD` | **Planned:** Agent supplies an uploaded file for processing by RAG. |

Results are ranked by vector similarity to `question_text`: index `0` is the closest match; later entries have equal or lower similarity.

## External Model API → Agent

| Interface | Description |
| --- | --- |
| `llm_api.generate_messages(messages: list[Message]) -> str` | Agent sends conversation messages through the external model wrapper and receives the model's JSON reply text. |

Input uses the same `Message(role, content)` structure, with `system`, `user`, or `assistant` roles. Agent includes its system prompt, conversation history, and current regulation evidence when available.

The wrapper always requests JSON object output and returns the reply content as a `str`, which Agent parses as a JSON object:

Direct answer:

```json
{"type": "answer", "content": "The answer."}
```

Retrieval request:

```json
{
  "type": "tool_call",
  "tool": "retrieve_regulations",
  "arguments": {"text": "password requirements"}
}
```

## Agent → Web API

| Interface | Description |
| --- | --- |
| `AgentService.respond(messages: list[Message]) -> list[Message]` | Web API supplies conversation history and receives new assistant and optional retrieval messages in display order. |
| `AgentService.process_file(file_path: Path) -> TBD` | **Planned:** Web API supplies an uploaded file for processing by Agent. |

Each `Message` is an immutable Python object with two fields:

- `role: Literal["user", "assistant", "system"]`: the message role.
- `content: str`: non-blank message text.

```python
Message(role="user", content="What does S17 require?")
```

The input is a non-empty `list[Message]` containing onl y `user` and `assistant` messages, ending with a `user` message. The output is a new `list[Message]`: one `assistant` message for a direct answer, or a retrieval `system` message followed by the `assistant` answer.

## Web API → Web UI

| Interface | Request body | Response body | Description |
| --- | --- | --- | --- |
| `POST /api/chat` | JSON: `{"messages": [...]}` | JSON: `{"messages": [...]}` | Web UI sends the full conversation and receives new assistant and optional retrieval messages. |
| `POST /api/files` | `multipart/form-data`, field `file` | `TBD` | **Planned:** Web UI uploads a file to Web API for Level 2 processing. |

Both `messages` fields are arrays of `ChatMessage` JSON objects: `role` is `"user"`, `"assistant"`, or `"system"`; `content` is a non-blank string.

Request example:

```http
POST /api/chat HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What does S17 require?"}
  ]
}
```

Response example with retrieval:

```json
{
  "messages": [
    {"role": "system", "content": "Regulation search: ...\nSearch results:\n..."},
    {"role": "assistant", "content": "The answer."}
  ]
}
```

Requests contain the full displayed history and end with a `user` message; any `system` messages are display-only and filtered before calling the Agent. Responses contain only new messages, which the frontend appends in order.

Planned file upload request example:

```sh
curl -X POST http://127.0.0.1:8000/api/files -F "file=@policy.pdf"
```
