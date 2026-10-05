"""Run the local browser UI and API from the scripts directory."""

import sys


def main() -> int:
    try:
        from run_web_ui import main as launch
    except ImportError as exc:
        print(
            f"Cannot load project dependencies: {exc}. "
            "Activate the fyp-security-compliance Conda environment first.",
            file=sys.stderr,
        )
        exit_code = 1
    else:
        exit_code = launch()

    if exit_code and sys.platform == "win32" and sys.stdin.isatty():
        try:
            input("Startup failed. Press Enter to close this window...")
        except (EOFError, KeyboardInterrupt):
            pass
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
