# S17/G3 AI Security Compliance Assistant: Plan and Progress

> This file records published plans, actual progress, and plan changes.

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
