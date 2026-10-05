"""Offline tests for starting and stopping both local servers."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("run_web_ui", ROOT / "scripts" / "run_web_ui.py")
assert SPEC is not None and SPEC.loader is not None
run_web_ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_web_ui)


class FakeProcess:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code
        self.terminated = False
        self.waited = False

    def poll(self) -> int | None:
        return 0 if self.terminated else self.exit_code

    def terminate(self) -> None:
        self.terminated = True

    def wait(self) -> int:
        self.waited = True
        return 0


def test_starts_both_and_stops_both_on_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []
    processes = [FakeProcess(), FakeProcess()]

    def fake_popen(
        args: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> FakeProcess:
        calls.append((args, cwd, env))
        return processes[len(calls) - 1]

    def interrupt(_: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(run_web_ui.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(run_web_ui.time, "sleep", interrupt)

    assert run_web_ui.main() == 0
    assert calls[0][0] == [sys.executable, str(ROOT / "scripts" / "run_web_api.py")]
    assert calls[0][2] is not None
    assert calls[0][2]["WEB_API_ALLOWED_ORIGINS"] == run_web_ui.UI_URL
    assert calls[1][0] == [
        sys.executable,
        "-m",
        "http.server",
        "5173",
        "--bind",
        "127.0.0.1",
        "--directory",
        str(ROOT / "src" / "web_ui"),
    ]
    assert all(cwd == ROOT for _, cwd, _ in calls)
    assert all(process.terminated and process.waited for process in processes)


def test_server_exit_closes_the_other(monkeypatch: pytest.MonkeyPatch) -> None:
    api, ui = FakeProcess(exit_code=3), FakeProcess()
    processes = iter([api, ui])
    monkeypatch.setattr(
        run_web_ui.subprocess, "Popen", lambda *args, **kwargs: next(processes)
    )

    assert run_web_ui.main() == 1
    assert ui.terminated and ui.waited


def test_partial_startup_failure_closes_first_server(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeProcess()
    results = iter([api, OSError("cannot start")])

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        result = next(results)
        if isinstance(result, OSError):
            raise result
        return result

    monkeypatch.setattr(run_web_ui.subprocess, "Popen", fake_popen)

    assert run_web_ui.main() == 1
    assert api.terminated and api.waited


def test_script_entrypoint_keeps_windows_failure_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_spec = importlib.util.spec_from_file_location("entry_run", ROOT / "scripts" / "run.py")
    assert entry_spec is not None and entry_spec.loader is not None
    entry_run = importlib.util.module_from_spec(entry_spec)
    entry_spec.loader.exec_module(entry_run)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import run_web_ui as launcher_module

    prompts: list[str] = []
    monkeypatch.setattr(launcher_module, "main", lambda: 1)
    monkeypatch.setattr(
        entry_run,
        "sys",
        SimpleNamespace(
            platform="win32",
            stdin=SimpleNamespace(isatty=lambda: True),
            stderr=io.StringIO(),
        ),
    )
    monkeypatch.setattr("builtins.input", prompts.append)

    assert entry_run.main() == 1
    assert prompts == ["Startup failed. Press Enter to close this window..."]
