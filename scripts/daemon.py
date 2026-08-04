#!/usr/bin/env python3
"""
JARVIS API Server launcher — runs uvicorn in a subprocess that survives parent death.
"""
import os
import sys
import subprocess
import signal
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

env = os.environ.copy()
env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__)) + "/.."

# Double-fork to daemonize
pid = os.fork()
if pid > 0:
    print(f"JARVIS daemon PID: {pid}")
    sys.exit(0)

# Child: detach from terminal
os.setsid()

pid2 = os.fork()
if pid2 > 0:
    sys.exit(0)

# Grandchild: actual server
os.umask(0)

# Redirect stdio
with open("/tmp/jarvis_daemon.log", "a") as log:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:app",
         "--host", "0.0.0.0", "--port", "8765", "--log-level", "warning"],
        stdout=log,
        stderr=log,
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
    )

with open("/tmp/jarvis.pid", "w") as f:
    f.write(str(proc.pid))

proc.wait()
