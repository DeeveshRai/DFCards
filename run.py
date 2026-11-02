"""Launch both local services, preferring the project's virtual environment."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent


def project_python():
    for relative in (".venv/Scripts/python.exe", ".venv/bin/python"):
        candidate = ROOT / relative
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def check_dependencies(python):
    result = subprocess.run(
        [python, "-c", "import uvicorn, fastapi, streamlit, requests, graphviz"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f'Dependencies are missing or unavailable for {python}.\n'
            f'Install them with:\n  & "{python}" -m pip install -r "{ROOT / "requirements.txt"}"'
        )


def main():
    processes = []
    try:
        python = project_python()
        check_dependencies(python)
        for port in (8000, 8501):
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    raise RuntimeError(f"Port {port} is already in use. Close the existing service and retry.")
        processes.append(subprocess.Popen([python, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT))
        wait_ready("http://127.0.0.1:8000/health", processes[0])
        env = os.environ.copy()
        env["DFCARDS_API_URL"] = "http://127.0.0.1:8000"
        processes.append(subprocess.Popen([python, "-m", "streamlit", "run", "frontend/app.py", "--server.address", "127.0.0.1", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats", "false"], cwd=ROOT, env=env))
        wait_ready("http://127.0.0.1:8501/_stcore/health", processes[1])
        print("DFCards is ready: http://127.0.0.1:8501", flush=True)
        webbrowser.open("http://127.0.0.1:8501")
        while all(p.poll() is None for p in processes):
            time.sleep(0.3)
        raise RuntimeError("An application service stopped unexpectedly.")
    except KeyboardInterrupt:
        print("\nStopping DFCards…")
    except (RuntimeError, OSError) as exc:
        print(f"Could not run DFCards: {exc}", file=sys.stderr)
        return 1
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return 0


def wait_ready(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Service failed to start; check its output above.")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}")


if __name__ == "__main__":
    raise SystemExit(main())
