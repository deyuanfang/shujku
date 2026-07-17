#!/usr/bin/env python3
"""PersonalKB Launcher — starts backend and frontend, opens browser."""

import subprocess
import sys
import time
import urllib.request
import os
import signal

BACKEND_PORT = 18765
FRONTEND_PORT = 5173
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def check_prerequisites():
    """Verify Python and Node are available."""
    try:
        subprocess.run([sys.executable, "--version"], capture_output=True, check=True)
    except Exception:
        print("ERROR: Python not found")
        return False
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except Exception:
        print("ERROR: Node.js not found. Install from https://nodejs.org/")
        return False
    return True

def install_backend_deps():
    """Install Python dependencies if needed."""
    try:
        import fastapi, uvicorn, sqlalchemy, jieba
        return True
    except ImportError:
        pass

    print("Installing backend dependencies (one-time, ~1-2 min)...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "fastapi", "uvicorn[standard]", "sqlalchemy", "aiosqlite",
         "jieba", "scikit-learn", "numpy", "python-multipart",
         "aiofiles", "pydantic", "pydantic-settings", "python-dotenv"],
        cwd=os.path.join(BASE_DIR, "backend"),
    )
    if result.returncode != 0:
        print("FAILED: Could not install backend dependencies")
        print("Run manually: cd backend && pip install -r requirements.txt")
        return False
    return True

def install_frontend_deps():
    """Install npm dependencies if needed."""
    frontend_dir = os.path.join(BASE_DIR, "frontend")
    node_modules = os.path.join(frontend_dir, "node_modules")
    dist = os.path.join(frontend_dir, "dist", "index.html")

    if not os.path.exists(node_modules):
        print("Installing frontend dependencies (one-time, ~3-5 min)...")
        result = subprocess.run(["npm", "install", "--silent"], cwd=frontend_dir)
        if result.returncode != 0:
            print("FAILED: npm install error")
            print("Run manually: cd frontend && npm install")
            return False

    if not os.path.exists(dist):
        print("Building frontend (one-time, ~30s)...")
        vite_bin = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")
        result = subprocess.run(["node", vite_bin, "build"], cwd=frontend_dir)
        if result.returncode != 0:
            print("WARNING: Frontend build failed, will try dev server")

    return True

def kill_port(port):
    """Kill any process listening on the given port."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        for line in out.split("\n"):
            if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                print(f"  Killed old process on port {port} (PID {pid})")
                time.sleep(1)
    except Exception:
        pass

def wait_for_url(url, timeout=15):
    """Wait until a URL becomes available."""
    for i in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False

def main():
    print()
    print("  ======================================")
    print("    PersonalKB - Personal Knowledge Base")
    print("  ======================================")
    print()
    print(f"  Python: {sys.version.split()[0]}")

    # Checks
    if not check_prerequisites():
        input("Press Enter to exit...")
        sys.exit(1)

    # Install deps
    if not install_backend_deps():
        input("Press Enter to exit...")
        sys.exit(1)
    if not install_frontend_deps():
        input("Press Enter to exit...")
        sys.exit(1)

    # Kill old processes
    print("\n  Cleaning old processes...")
    kill_port(BACKEND_PORT)
    kill_port(FRONTEND_PORT)
    time.sleep(1)

    # Start backend
    print(f"\n  Starting backend on port {BACKEND_PORT}...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT),
         "--log-level", "warning"],
        cwd=os.path.join(BASE_DIR, "backend"),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    if wait_for_url(f"http://127.0.0.1:{BACKEND_PORT}/health"):
        print(f"  Backend ready:  http://127.0.0.1:{BACKEND_PORT}")
    else:
        print(f"  WARNING: Backend startup timeout")

    # Start frontend
    print(f"\n  Starting frontend on port {FRONTEND_PORT}...")
    vite_bin = os.path.join(BASE_DIR, "frontend", "node_modules", "vite", "bin", "vite.js")
    frontend_proc = subprocess.Popen(
        ["node", vite_bin, "--host", "127.0.0.1", "--port", str(FRONTEND_PORT), "--strictPort"],
        cwd=os.path.join(BASE_DIR, "frontend"),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    if wait_for_url(f"http://127.0.0.1:{FRONTEND_PORT}"):
        print(f"  Frontend ready: http://127.0.0.1:{FRONTEND_PORT}")
    else:
        print(f"  WARNING: Frontend startup timeout")

    # Open browser
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")

    print()
    print("  ======================================")
    print(f"    Backend : http://127.0.0.1:{BACKEND_PORT}")
    print(f"    Frontend: http://127.0.0.1:{FRONTEND_PORT}")
    print("  ======================================")
    print()
    print("  Press Ctrl+C to stop all services...")

    try:
        # Keep running until user presses Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n  Stopping services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
            frontend_proc.wait(timeout=5)
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()
        print("  Services stopped.")

if __name__ == "__main__":
    main()
