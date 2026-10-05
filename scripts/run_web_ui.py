"""Run the local API and static web UI together."""

import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_URL = "http://127.0.0.1:5173"


def main() -> int:
    processes: list[subprocess.Popen[bytes]] = []
    try:
        api_env = os.environ.copy()
        api_env["WEB_API_ALLOWED_ORIGINS"] = UI_URL
        processes.append(
            subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "run_web_api.py")],
                cwd=ROOT,
                env=api_env,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "http.server",
                    "5173",
                    "--bind",
                    "127.0.0.1",
                    "--directory",
                    str(ROOT / "src" / "web_ui"),
                ],
                cwd=ROOT,
            )
        )
        print(f"Open {UI_URL} after both servers start. Press Ctrl+C to stop.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        print("A server stopped; closing the other one.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"Could not start servers: {exc}", file=sys.stderr)
        return 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
