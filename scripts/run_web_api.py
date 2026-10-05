"""Run the local HTTP API for the security compliance Agent."""

import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from web_api.app import app


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
