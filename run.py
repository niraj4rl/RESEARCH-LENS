#!/usr/bin/env python3
"""Launch the ResearchLens Streamlit application."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
APP_FILE = ROOT_DIR / "streamlit_app.py"


def find_python() -> str:
    candidates = [
        ROOT_DIR / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python"),
        ROOT_DIR / "backend" / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return sys.executable or shutil.which("python") or "python"


def main() -> int:
    python_exe = find_python()
    command = [python_exe, "-m", "streamlit", "run", str(APP_FILE)]
    print("Starting ResearchLens Streamlit app at http://localhost:8501")
    try:
        return subprocess.call(command, cwd=ROOT_DIR)
    except FileNotFoundError:
        print("Streamlit is not installed. Run: python -m pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
