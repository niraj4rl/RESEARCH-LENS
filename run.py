#!/usr/bin/env python3
"""
ResearchLens Unified Single-Command Runner
Launches both the FastAPI backend (port 8000) and Next.js frontend (port 3000)
with automatic environment detection, dependency syncing, and graceful shutdown.
"""

import os
import sys
import subprocess
import time
import signal
import shutil
import urllib.request

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

def print_banner():
    print("=" * 64)
    print("   ResearchLens — Scholarly Research-Gap Discovery System   ")
    print("=" * 64)

def find_python():
    """Find a functional Python interpreter."""
    # 1. Virtual environment python in backend
    venv_python = (
        os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe")
        if os.name == "nt"
        else os.path.join(BACKEND_DIR, "venv", "bin", "python")
    )
    if os.path.isfile(venv_python):
        return venv_python

    # 2. Virtual environment python in root
    root_venv_python = (
        os.path.join(ROOT_DIR, "venv", "Scripts", "python.exe")
        if os.name == "nt"
        else os.path.join(ROOT_DIR, "venv", "bin", "python")
    )
    if os.path.isfile(root_venv_python):
        return root_venv_python

    # 3. Current running interpreter
    if sys.executable:
        return sys.executable

    # 4. Standard path checks on Windows
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local_app_data, "Programs", "Python", "Python312", "python.exe"),
            os.path.join(local_app_data, "Programs", "Python", "Python311", "python.exe"),
            "C:\\Python312\\python.exe",
            "C:\\Python311\\python.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

    py = shutil.which("python") or shutil.which("python3") or shutil.which("py")
    return py or "python"

def find_npm():
    """Find npm executable."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm:
        return npm
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\nodejs\npm.cmd",
            os.path.expandvars(r"%APPDATA%\npm\npm.cmd"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
    return "npm"

def check_docker():
    """Try to start Docker if available; fallback silently to SQLite."""
    print("\n[1/3] Database initialization...")
    docker = shutil.which("docker")
    if docker:
        try:
            res = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                print("  [OK] PostgreSQL container running on port 5433.")
                return
        except Exception:
            pass
    print("  [INFO] Using embedded zero-config SQLite database (researchlens.db).")

def check_backend_deps(python_exe):
    """Ensure backend requirements are installed."""
    try:
        res = subprocess.run(
            [python_exe, "-c", "import fastapi, uvicorn, sqlalchemy; print('OK')"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and "OK" in res.stdout:
            return
    except Exception:
        pass

    print("  Installing backend dependencies...")
    req_file = os.path.join(BACKEND_DIR, "requirements.txt")
    subprocess.run([python_exe, "-m", "pip", "install", "-r", req_file, "-q"], cwd=BACKEND_DIR)

def check_frontend_deps(npm_cmd):
    """Ensure frontend dependencies are installed."""
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print("  Installing frontend packages (npm install)...")
        subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR, shell=True)

def wait_for_backend(port=8000, timeout=15):
    """Wait until backend responds to health check."""
    start_time = time.time()
    url = f"http://127.0.0.1:{port}/health"
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def main():
    print_banner()

    python_exe = find_python()
    npm_cmd = find_npm()

    # Step 1: Database
    check_docker()

    # Step 2: Backend check
    print("\n[2/3] Checking dependencies & launching Backend (Port 8000)...")
    check_backend_deps(python_exe)
    
    # Step 3: Frontend check
    print("\n[3/3] Checking dependencies & launching Frontend (Port 3000)...")
    check_frontend_deps(npm_cmd)

    # Launch Backend
    backend_cmd = [python_exe, "main.py"]
    print(f"  Starting FastAPI: {' '.join(backend_cmd)}")
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=BACKEND_DIR,
    )

    # Launch Frontend
    frontend_cmd = [npm_cmd, "run", "dev"]
    print(f"  Starting Next.js: {' '.join(frontend_cmd)}")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=FRONTEND_DIR,
        shell=True,
    )

    # Wait for backend health check
    backend_ready = wait_for_backend(8000, timeout=12)

    print("\n" + "=" * 64)
    print("  ResearchLens is up and running!")
    print("=" * 64)
    print("  • Frontend App:   http://localhost:3000")
    print("  • Backend API:    http://localhost:8000/docs")
    print(f"  • Health Status:  {'HEALTHY [OK]' if backend_ready else 'STARTING...'}")
    print("=" * 64)
    print("  Press Ctrl+C to stop all servers.\n")

    def shutdown(sig, frame):
        print("\n[SHUTDOWN] Terminating servers...")
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        try:
            backend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # Keep alive and monitor child processes
    try:
        while True:
            b_poll = backend_proc.poll()
            f_poll = frontend_proc.poll()
            if b_poll is not None:
                print(f"[ERROR] Backend exited unexpectedly with code {b_poll}")
                break
            if f_poll is not None:
                print(f"[ERROR] Frontend exited unexpectedly with code {f_poll}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
