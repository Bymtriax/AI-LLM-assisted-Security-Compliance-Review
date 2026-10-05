# S17/G3 AI Security Compliance Assistant: Plan and Progress

> This file records published plans, actual progress, and plan changes.

## Current Repository Structure

- `src/` contains `corpus_builder/`, `api/`, `rag/`, `agent/`, `web_api/`, and `web_ui/`; `tests/` mirrors these modules and also covers `scripts/`.
- `scripts/` contains corpus building, API checks, terminal chat, vector queries, local web startup, and standalone S17/G3 PDF-to-JSON commands.
- `docs/FRAMEWORK.md` records the directory tree; `docs/INTERFACE.md` records current module interfaces.
- `data/raw/` and `data/processed/` are ignored local data directories. Existing `data/vector_db/` files remain tracked; `exp/` ignores new untracked experimental files.

## Plan (not implemented)

### Hybrid RAG retrieval

- [ ] Add BM25 keyword retrieval.

## Progress (implemented)

### Organize source regulations

- Archived the existing Simplified Chinese S17/G3 source files under `data/raw/standards/zh-Hans/`.
- Downloaded the official English S17 v8.2 and G3 v10.2 from GovCERT and stored them under `data/raw/standards/en/`.
- Added `docs/STANDARDS.md` to record file sources and storage rules.
- Confirmed that Plan 1 uses English S17/G3 as its primary corpus; Chinese source files are retained for a separate Chinese index in the future.

### Organize the project directory

- Moved project documentation into `docs/`.
- Kept original regulations under `data/raw/standards/`.
- Established the `src/`, `scripts/`, `tests/`, and `data/` directory structure.
- Moved the embedding API connectivity script into `scripts/` and changed it to read the API key from environment variables.
- Added `.env.example` and `.gitignore` to avoid committing secrets, vector databases, user uploads, and temporary data.

### Decide Python environment management

- Decided to use Conda for Python environment management.
- Added `environment.yml`, defining the `fyp-security-compliance` environment, Python 3.12, and pip.
- Created the `fyp-security-compliance` environment through `D:\app\conda\Scripts\conda.exe`.
- Verified that the environment uses Python 3.12.13.

### Separate regulation sources from corpus-building code

- Kept only regulation corpus-building code in `src/corpus_builder/`.
- Moved the Chinese and English S17/G3 source files into `data/raw/standards/`.
- Moved the standards source inventory to `docs/STANDARDS.md`.
- Removed the empty placeholder `src/api/` directory.

### S17 chunking experiment

- Added and installed `pypdf` through `environment.yml`.
- Added `exp/build_s17_chunks.py`.
- Split the 45-page English S17 into 183 structured chunks: 155 numbered clauses and 28 section descriptions.
- Produced `exp/output/s17_en_chunks.jsonl` and `exp/output/s17_en_chunk_report.json`.
- Verified selected control clauses and their page numbers, and confirmed that chunks do not contain duplicate headers or footers.
- Did not yet build a vector database or implement queries.
- Identified that some chunks were too long and required further splitting in a V2 experiment.

### S17 chunking V2 experiment

- Retained V1 `exp/build_s17_chunks.py` and its output as a clause-number-based baseline.
- Added `exp/build_s17_chunks_v2.py` to build V2 results directly from the English S17 PDF.
- Made V2 recognize clause numbers without a trailing period, separating the previously joined `5.2.4 / 5.2.5` and `7.2.1 / 7.2.2` clauses.
- Made V2 subdivide structured chunks longer than 220 English words using internal headings, bullet points, lettered terms, or paragraph batches.
- Produced 186 structured chunks and 225 retrieval chunks.
- Generated `exp/output/s17_en_retrieval_chunks_v2.jsonl`, a Markdown review file, and an experiment report.
- Verified that all 186 parent chunks were fully covered, all 225 IDs were unique, and no chunk exceeded 300 English words.
- Did not yet build a vector database or implement queries.

### Embedding database experiment: input format decision

- Limited embedding model input to `section`, `parent_titles`, and clause `text`.
- Excluded `document`, `version`, page numbers, source files, and chunk IDs from embeddings, retaining them as vector database metadata.
- Set the next step to read V2 JSONL and validate API input-to-vector ID mapping with a small number of chunks.

### S17 ChromaDB database experiment

- Selected ChromaDB as the local embedded vector database and installed `chromadb` in the Conda environment.
- Added `exp/build_s17_chroma_db.py` to read V2 JSONL, construct embedding input, call the SiliconFlow API in batches, and write to ChromaDB.
- Fixed experiment batches at eight items because SiliconFlow resets response indexes for requests larger than eight, preserving the one-to-one mapping between chunk IDs and vectors.
- Built `data/vector_db/s17_chroma_experiment/` with the collection `s17_en_v8_2_experiment`.
- Completed the database with all 225 input chunks matching database records and no missing or additional IDs; used `Qwen/Qwen3-VL-Embedding-8B` with 4,096-dimensional vectors.
- Generated a local `manifest.json` containing the input, model, dimensions, batch size, and build time.
- Verified retrieval: a test question about encryption requirements for transmitting confidential information returned relevant clauses including S17 15.2.2.

### Interactive S17 ChromaDB retrieval test

- Added `exp/test_s17_chroma_retrieval.py`.
- Made the program read user input, generate a question vector with the same embedding model used for database construction, and return the three most relevant S17 results from local ChromaDB.
- Displayed each result's chunk ID, clause number, parent section, source page, cosine distance, and original regulation text.

### Formal regulation corpus code: module responsibility decision

- Assigned each regulation an independent `build` program responsible for reading its PDF, filtering and splitting according to its structure, calling the embedding module, and calling the Chroma module for storage.
- Defined the embedding module as a shared module that accepts text and returns vectors.
- Defined the Chroma module as a shared module providing interfaces for storing new vectors and querying nearby vectors.
- Set the next step to organize the S17 experimental code into formal code under `src/` according to these responsibilities.

### Embedding API module

- Added `src/api/embedded_api.py`.
- Exposed only two public interfaces: `embed_text(text)` and `embed_texts(texts)`.
- Made the module read the SiliconFlow key from local `.env` and process internally in batches of eight so the API response order can be verified.
- Verified against the real service that a single input returns a 4,096-dimensional vector and nine batched inputs return nine 4,096-dimensional vectors.

### Embedding API QA tests

- Added `tests/api/test_embedded_api.py`, directly importing and testing `src/api/embedded_api.py`.
- Used pytest `monkeypatch` to temporarily replace the network request function during tests, avoiding real API calls and quota consumption.
- Covered single input, automatic splitting of nine items into 8 + 1, an empty list, empty text, and an invalid API response index.
- Installed pytest and ran the suite with seven tests passing.

### Vector Store module

- Added `src/corpus_builder/vector_store.py`, using local ChromaDB internally.
- Exposed `store_vector(record, vector)`, `store_vectors(records, vectors)`, and `query_vectors(vector, top_k=3)`.
- Kept the vector store limited to vectors and regulation records without calling the embedding API.
- Added `tests/corpus_builder/test_vector_store.py`, using temporary ChromaDB instances to test storage, queries, batch ordering, and input validation.
- Ran QA with four tests passing.

### Formal S17 handler

- Added `src/corpus_builder/handle_s17.py` to read the complete English S17 PDF and generate records ready for the vector store according to the regulation's structure.
- Defined the formal output as `id`, `text`, and `metadata`, with metadata preserving section, version, language, pages, source, and split-tracking information.
- Simplified embedding API input to a plain `text` array; other information does not participate in embedding.
- Made `main()` call the existing `embedded_api.embed_texts()` and `vector_store.store_vectors()` for the final two steps.
- Added `tests/corpus_builder/test_handle_s17.py`; the complete QA suite had 15 tests passing.
- Verified against the official S17 v8.2 PDF: after filtering residual `INFORMATION SECURITY` headers, generated 224 records with unique IDs and lengths ranging from 7 to 220 English words.
- Completed the formal S17 database build: generated 224 4,096-dimensional vectors with `Qwen/Qwen3-VL-Embedding-8B` and wrote them to the shared Chroma collection `security_standards`; total records, S17 records, and unique IDs all equaled 224.
- Set the next step to implement or validate the formal regulation retrieval workflow.

### Embedding context for the formal database

- Changed the formal S17 build to embed the clause number, parent section titles, and clause text together.
- Continued storing the original clause text as the database document for result display, citation, and answer generation.
- Kept this format consistent with the earlier ChromaDB experiment so short clauses retain their regulatory domain and topic context.
- Deleted and rebuilt the shared Chroma collection to avoid mixing older text-only vectors with new contextual vectors.

### Vector Store query record type

- Changed `query_vectors(vector, top_k=3)` to return similarity-ordered `list[CorpusRecord]` and stopped exposing Chroma distance as a public result field.
- Changed the interactive query script to read the record `id`, `text`, and metadata directly.
- Changed Vector Store tests to verify `CorpusRecord` query results and complete metadata round trips.
- Ran the full offline suite with 42 tests passing.

### Narrow S17 Handler responsibilities

- Changed `handle_s17(pdf_path: Path)` to require a PDF path and only return `list[CorpusRecord]`.
- Removed embedding, ChromaDB writing, and the command-line entry point from the handler; these are now handled by the unified build orchestrator.
- Changed tests to verify the required-path contract and stopped testing the removed build orchestration flow.

### Unified regulation corpus build entry point

- Added `src/corpus_builder/build_corpus.py` to call registered handlers in sequence, merge their `CorpusRecord` results, and complete the existing embedding and ChromaDB write workflow.
- Added `scripts/build_corpus.py` as the command entry point for launching the unified build from the project root.
- Registered S17 as the current handler; future regulation handlers only need to be added to `HANDLERS`.
- Added cross-handler record ID uniqueness validation before calling the embedding API, preventing duplicate records from being written.
- Did not build a BM25 index in this change; BM25 will be added later.
- Ran the full offline suite with 44 tests passing.

### S17 record retrieval text

- Changed the S17 handler to write `Section`, `Parent sections`, and `Text` directly into `CorpusRecord.text` using a three-line format.
- Made the unified builder pass `record.text` unchanged to the embedding API; the ChromaDB document and query results also retain the same context.
- Changed `text_sha256` to represent the complete retrieval text actually stored.
- Changed all corpus test fixtures to use contextual S17 `text`; the one-time embedding API check script now uses and validates the same format.
- Ran the full offline suite with 51 tests passing.

### RAG Retriever and Agent-facing service

- Added a configurable `Retriever` type in `src/rag/retriever.py` and a `RAGService` type in `src/rag/rag_service.py` as the Agent-facing interface.
- Made Retriever call `api/embedded_api.py` to vectorize Agent-supplied text and call `corpus_builder/vector_store.py` for similarity retrieval.
- Made the interface return `list[str]` by preserving the vector store's most-to-least relevant order and extracting each `CorpusRecord.text`.
- Added offline tests for service delegation, API and vector-store coordination, result ordering, an empty database, and input validation; the tests do not call the real embedding API or database.
- Deferred result post-processing to later changes.

### SiliconFlow chat-completions API wrapper

- Added `src/api/llm_api.py` as the generation-model boundary for the future Agent module.
- Simplified the public interface to `generate_text(text) -> str`: it sends one text to the fixed DeepSeek-V4-Flash model and returns the reply text.
- Reused the existing local `SILICONFLOW_API_KEY` configuration and set `deepseek-ai/DeepSeek-V4-Flash` as the default generation model.
- Added `exp/test_siliconflow_chat.py` for a one-time real connectivity check with a short security-compliance prompt.
- Added offline tests for request construction, response extraction, input validation, missing credentials, and malformed responses; tests do not call the real API.
- Verified the experiment against the real service: DeepSeek-V4-Flash returned a valid concise compliance concern using the existing local API key.
- Added `scripts/check_llm_api.py` for manually entering one text, printing one model reply, and then exiting.

### Chat API message type

- Added `Message` in `src/api/models.py` with `role` and `content` fields for the chat API and Agent conversation history.
- Added `generate_messages(messages) -> str`; the existing `generate_text(text) -> str` remains as the simple one-text interface.
- Added a focused offline test for the new type.

### Basic Agent conversation service

- Added `AgentService.respond(text) -> str` with an internal message list.
- Made each response include the accumulated user and assistant conversation, then store the new assistant reply.
- Deferred tool decisions and RAG orchestration.
- Added `scripts/chat_agent.py` as a terminal conversation entry point that reuses one `AgentService` until the user enters `exit` or `quit`.
- Added a separate Agent system prompt describing the conversation context, decision flow, and JSON format for direct answers or the `retrieve_regulations` tool.
- Made `AgentService` prepend the system prompt to every model request without storing it in conversation history.
- Added JSON response parsing and one direct `retrieve_regulations` tool path to `AgentService`.
- Made each retrieval append one visible system message containing the query and joined `list[str]` results; tool-call JSON remains internal.
- Added a copied `AgentService.messages` view and made the terminal script display new retrieval system messages before the final answer.
- Colored terminal speaker labels for readability: user green, Agent blue, and system retrieval messages yellow.
- Declared in the Agent prompt that the current knowledge base contains only English S17 v8.2, and required explicit disclosure when requested material is outside that scope.

### Stateless Agent conversation input

- Changed `AgentService.respond()` to accept the complete caller-managed `list[Message]`, ending with a user message, and return the answer without retaining or modifying conversation history.
- Kept the Agent system prompt and current-turn regulation evidence inside the model request; rejected caller-supplied `system` messages.
- Added an optional retrieval callback so the terminal script can continue displaying regulation search results while managing its own user/assistant history.
- Updated offline tests for supplied history, isolated conversations, temporary retrieval evidence, input validation, and terminal conversation handling.
- Ran the full offline suite with 75 tests passing.

### Initial HTTP chat API

- Added `src/web_api/app.py` with `POST /api/chat`: the caller sends the complete user/assistant conversation, and the response contains one new assistant message.
- Validated message roles, non-blank content, a non-empty conversation, and a final user message before calling a fresh `AgentService`; no conversation is stored by the server.
- Added `scripts/run_web_api.py` for local Uvicorn startup and configurable browser origins through `WEB_API_ALLOWED_ORIGINS`.
- Added FastAPI, Pydantic, Uvicorn, and HTTPX to `environment.yml` and documented the request and response in `README.md`.
- Added offline HTTP tests with a mocked Agent and no external API calls.
- Ran the full offline suite with 83 tests passing; a local Uvicorn check returned `200` for `/openapi.json` and `422` for an invalid chat request.

### Return retrieval messages from the chat API

- Changed the chat response to a `messages` array in display order: a direct answer returns one `assistant` message; a RAG-assisted answer returns the Agent's retrieval `system` message followed by its `assistant` answer.
- The retrieval message includes the search query and retrieved regulation texts already produced by the Agent; no separate retrieval field was added.
- Allowed previously returned `system` messages in subsequent requests for display continuity, while excluding them from the conversation passed to the Agent.
- Updated the HTTP tests and the public API examples for both response paths.
- Ran the full offline suite with 85 tests passing.

### Diagnose malformed model replies after RAG

- Added offline Agent tests that distinguish malformed replies during the initial decision from malformed replies after regulation retrieval, including empty, plain-text, and Markdown-fenced output.
- Moved the retrieval callback to immediately after RAG returns evidence, before the final model request; the terminal script now shows that evidence in yellow even if the final reply fails.
- Made Agent parsing errors identify the failed phase and output category without displaying raw model text. A failed terminal turn is not added to conversation history.
- Ran the full offline suite with 92 tests passing and one dependency deprecation warning.

### Show malformed model replies in the terminal

- Added `ModelResponseError` to carry the complete raw reply separately from its safe error message when model JSON or expected answer/retrieval-call fields are invalid.
- Made `scripts/chat_agent.py` print the raw reply with `repr()` on this error, including after a RAG-assisted final reply fails; the HTTP chat API does not return the raw reply.
- Added offline tests for the original reply on initial and post-retrieval errors, invalid answer and retrieval-call fields, terminal display, and exclusion from the HTTP error response.
- Ran the full offline suite with 99 tests passing and one dependency deprecation warning.

### Minimal browser chat UI

- Added a standalone HTML, CSS, and JavaScript frontend under `src/web_ui/` with a large conversation area, a text input, and a send button.
- Made the page send the full displayed history to `POST /api/chat`, render returned retrieval messages in yellow before the assistant reply, and keep history only in browser memory. Failed sends retain the draft for retry.
- Documented separate local startup with Python's static HTTP server at `127.0.0.1:5173` and the API at `127.0.0.1:8000`, including `WEB_API_ALLOWED_ORIGINS` configuration.
- Verified four offline Node tests for request history, response order, browser fetch binding, and failed-request handling; the Python suite remains at 99 passing tests with one dependency deprecation warning.
- A browser smoke check with a local mock API displayed a direct reply and a retrieval message followed by an assistant reply; no real model call was made.

### One-command local web startup

- Added `scripts/run_web_ui.py` to launch the existing API and the Python static frontend server from one command in the active Python environment.
- The launcher stops the other server if either exits and stops both on Ctrl+C; ports 8000 and 5173 must be available.
- Added three offline launcher tests for both startup commands, Ctrl+C cleanup, early server exit, and partial startup failure. The full Python suite passes 102 tests with one dependency deprecation warning; the four Node frontend tests also pass.
- A live combined-start check encountered an existing process on port 8000, so simultaneous startup was not verified on that port in this run.

### Local web startup follow-up

- The combined launcher now adds the local UI origin to the API child process's allowed origins, preserving other configured origins without editing `.env`.
- Five offline launcher tests pass; the full Python suite has 104 passing tests with one dependency deprecation warning, and the four Node frontend tests pass. After the previous API process was stopped, a live combined startup served the UI and API with HTTP `200`, and the UI-origin CORS preflight returned `200`. No real model request was made.

### Verified web launcher status and shutdown

- Added `scripts/run.py` and made the combined launcher check ports, confirm both HTTP services and API browser access, then print the Web UI address only after all checks succeed.
- Startup failure identifies the affected service; an occupied-port check starts no processes. A later service exit or Ctrl+C closes both launched processes. Interactive Windows failures remain visible until Enter is pressed.
- Eight offline launcher tests pass, including the interactive Windows failure message. The full Python suite has 107 passing tests with one dependency deprecation warning, and the four Node frontend tests pass. A live launch reported both services ready, a second launch reported occupied ports, and Ctrl+C released ports 8000 and 5173. No real model request was made.

### Simplified web launcher

- Reduced `scripts/run_web_ui.py` to starting the API and static UI processes, printing the address, and stopping both on Ctrl+C or when either process exits. Removed port probes and HTTP and CORS health checks; the API child still allows the local UI origin.
- Four focused launcher tests pass; the full Python suite has 103 passing tests with one dependency deprecation warning. The four Node frontend tests remain unchanged.
- During a live check, another local process occupied port 8000. The simplified launcher exited and cleaned up its own UI process. The already-running UI and API returned HTTP `200`, including the browser-origin CORS preflight; no real model request was made.

### Standalone English S17/G3 JSON preprocessing

- Added `src/corpus_builder/split_pdf.py`, extracted from the original S17 splitting workflow, and `scripts/split_pdfs.py` to process both configured English PDFs with one command.
- Retained `CorpusRecord` and the `id`, `text`, `metadata` JSON structure, including section context, source paths, starting pages, split tracking, word counts, and text hashes.
- Added support for G3's different front-matter length, numbering without trailing periods, lettered headings identified from the contents, appendices A-D, and unlabelled appendix continuation pages. Preserved recognizable body titles where contents wording differs and prevented cross-references from changing chapter ownership.
- Generated `data/processed/s17_en_chunks.json` with 224 records from 185 parent chunks, and `data/processed/g3_en_chunks.json` with 896 records from 172 parent chunks. S17 retains its original record IDs while the new parser removes wrapped running-header remnants and completes wrapped chapter titles.
- Verified both local outputs for unique IDs, valid text hashes, preservation of every extracted parent passage through semantic subdivision, and a maximum of 220 English words in the generated passages. All 125 lettered G3 contents entries have corresponding section IDs.
- Added eight offline preprocessing tests; the full Python suite passed with 111 tests and one existing dependency deprecation warning. No real embedding or generation API was called.
- Added `data/processed/` to `.gitignore`. Source PDFs, the existing builder, and the vector database were not modified. JSON consumption by the builder remains a later refactor; table and diagram layout is not reconstructed, and split parts retain parent starting-page metadata.

### Enable JSON mode for Agent replies

- Added the optional `json_mode` keyword argument to `src/api/llm_api.py`; when enabled, the request includes `response_format={"type": "json_object"}`. Default text calls still use the existing behavior and return the model reply string.
- Enabled JSON mode for both Agent model requests: the initial answer-or-retrieval decision and the final answer after retrieval. The existing prompt and field checks still define and validate `answer` and `tool_call`; JSON mode does not guarantee those fields or content correctness, and no JSON Schema constraints or automatic retries were added.
- Verified 22 focused offline tests and the full Python suite with 113 passing tests and one existing dependency deprecation warning. Tests mock external services and cover optional request formatting, reply preservation, both Agent request stages, and rejection of invalid Agent fields.
- A manual real request to `deepseek-ai/DeepSeek-V4-Flash` with the Agent prompt and a short greeting returned a parseable `answer` JSON object. No regulation retrieval was performed in that manual check.

### Unified Agent response messages

- Changed the Agent interface to `AgentService.respond(messages: list[Message]) -> list[Message]` and removed the `on_retrieval` callback. Direct answers return one `assistant` message; RAG-assisted answers return the retrieval `system` message followed by the `assistant` answer.
- Updated the Web API to convert and return all Agent messages in order, and the terminal script to display them while retaining only user/assistant history. The frontend already appends every returned message; the HTTP request and response format remains unchanged.
- Messages are delivered only after a successful response. A failure returns no partial retrieval messages and does not enter conversation history; existing error diagnosis and terminal raw-reply display are preserved.
- Updated `docs/INTERFACE.md` and the offline tests. All 34 focused Python tests, all 115 Python tests, and five Node frontend tests pass, with one existing dependency deprecation warning in the Python suite. Tests cover message order, multiple returned messages, empty retrieval results, conversation isolation, and failed-turn handling; no real embedding or generation API was called.

### Mandatory JSON model output

- Simplified the model interface to `generate_messages(messages: list[Message]) -> str` by removing `json_mode`; every request now includes `response_format={"type": "json_object"}`. The `generate_text(text: str) -> str` helper uses the same mandatory JSON output.
- Removed the option from Agent calls and test doubles, and updated `docs/INTERFACE.md`. The wrapper returns JSON reply text as a string; Agent continues parsing and validating `answer` and `tool_call` responses with the existing error diagnosis.
- All 22 focused offline tests and all 114 Python tests pass, with one existing dependency deprecation warning in the full suite. Tests verify mandatory JSON request formatting, reply preservation, and both Agent request stages; no real embedding or generation API was called.

```markdown
## Update format

### Update title

- Completed:
- Test result:
- New decision:
- Plan change: none / describe the change
- Risk or blocker:
- Next step:
```
