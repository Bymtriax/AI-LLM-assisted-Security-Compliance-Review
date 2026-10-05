# S17/G3 AI Security Compliance Review

An AI-assisted security-compliance review project using Hong Kong S17 and G3 as the initial reference corpus.

## Project documents

- [System framework](docs/FRAMEWORK.md)
- [Process and plan](docs/PROCESS_AND_PLAN.md)

## Python environment

This project uses Conda. After Conda is installed, create and activate the project
environment from the repository root:

```powershell
conda env create -f environment.yml
conda activate fyp-security-compliance
```

When `environment.yml` changes:

```powershell
conda env update -f environment.yml --prune
```

## Directory overview

```text
docs/       Public English architecture and roadmap documentation
src/        Main application code
scripts/    Manual developer commands
tests/      Automated tests
data/       Raw, generated, and private data (not committed)
```

## Run the basic terminal chat

Activate the project environment from the repository root:

```powershell
conda activate fyp-security-compliance
```

Copy `.env.example` to `.env` if needed, then set your local SiliconFlow API
key. Never commit the `.env` file.

```dotenv
SILICONFLOW_API_KEY=your_key_here
```

Start the chat:

```powershell
python scripts/chat_agent.py
```

## Run the local chat API

Activate the Conda environment and set `SILICONFLOW_API_KEY` in your local
`.env` file. If a browser frontend runs on another origin, set
`WEB_API_ALLOWED_ORIGINS` to its exact origin (or a comma-separated list of
origins). An empty value disables cross-origin browser requests.

```powershell
python scripts/run_web_api.py
```

The server listens on `http://127.0.0.1:8000`. Its API documentation is at
`http://127.0.0.1:8000/docs`. Send the displayed conversation, including the
latest user message, to `POST /api/chat`:

```json
{"messages":[{"role":"user","content":"What does S17 require?"}]}
```

The response contains new messages in display order. A direct answer has one
assistant message; a retrieval-assisted answer has a system message containing
the search query and results, followed by the assistant message. Append the
returned messages to the frontend conversation:

```json
{"messages":[{"role":"assistant","content":"..."}]}
```

The frontend may send those system retrieval messages back with later requests.
The server excludes them from the conversation passed to the Agent.

## Run the minimal web UI

This frontend uses plain HTML, CSS, and JavaScript. No frontend package install
is needed. Set the API key in your local `.env`:

```dotenv
SILICONFLOW_API_KEY=your_key_here
```

The combined launcher automatically allows `http://127.0.0.1:5173` to call its
API process. If you start the API separately, set `WEB_API_ALLOWED_ORIGINS` in
`.env` as described above. From the project root, start both servers with one
command:

```powershell
conda activate fyp-security-compliance
python .\scripts\run.py
```

The script prints `http://127.0.0.1:5173`; open it after both servers have
started. If either server exits, the script closes the other one. The page sends the full displayed
conversation to the API, shows returned retrieval messages in yellow, and keeps
history only until the page is refreshed. Press Ctrl+C to stop both servers.
Restart the script after changing `.env`. Stop any servers already using ports
8000 or 5173 before starting it.
