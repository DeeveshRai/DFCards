import socket
import subprocess

import pytest

import run


def test_prefers_project_environment_over_system_python(tmp_path, monkeypatch):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run.sys, "executable", "system-python-without-dependencies")
    assert run.project_python() == str(python)


def test_missing_dependencies_give_install_command(monkeypatch):
    monkeypatch.setattr(run.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1))
    with pytest.raises(RuntimeError, match="pip install -r"):
        run.check_dependencies("python-without-dependencies")


def test_launcher_starts_and_stops_both_services(tmp_path, monkeypatch):
    for port in (8000, 8501):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                pytest.skip(f"Local port {port} is already in use")
    monkeypatch.setenv("DFCARDS_DATA_DIR", str(tmp_path))
    processes = []
    original = subprocess.Popen
    # Dependency checking uses subprocess.run; keep its short-lived process
    # separate from the two long-running application services tracked below.
    run.check_dependencies(run.project_python())
    monkeypatch.setattr(run, "check_dependencies", lambda python: None)

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    def browser(url):
        assert url == "http://127.0.0.1:8501"
        # Simulate interruption once both health checks have passed.
        raise KeyboardInterrupt

    monkeypatch.setattr(run.subprocess, "Popen", spawn)
    monkeypatch.setattr(run.webbrowser, "open", browser)
    assert run.main() == 0
    assert len(processes) == 2
    assert all(process.poll() is not None for process in processes)
