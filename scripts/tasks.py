"""Helpers for the shortcut tasks in pyproject.toml (`uv run poe <task>`). Standard library only.

- `stop --port N` stops the factordesk server on a local port. It stops a process only after
  `/api/health` on that port answers like factordesk, so it never stops another program.
- `npm ARGS...` runs npm with ARGS. On Windows npm is `npm.cmd`, which a task runner cannot start
  by name, so this finds it on PATH first.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


def is_factordesk(port: int) -> bool | None:
    """True: factordesk answers on the port. False: another program. None: nothing answers."""
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("status") == "ok" and "schema_version" in body


def listening_pids(port: int) -> set[int]:
    """Process ids listening on the TCP port, from netstat (Windows) or lsof (macOS, Linux)."""
    pids: set[int] = set()
    if sys.platform == "win32":
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, check=False
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
                pids.add(int(parts[4]))
    elif shutil.which("lsof"):
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        pids.update(int(p) for p in out.split() if p.isdigit())
    pids.discard(0)
    return pids


SERVE = re.compile(r"factordesk(?:\.exe)?\"?\s+serve\b(?P<rest>.*)", re.IGNORECASE)
PORT_FLAG = re.compile(r"--port[=\s]+(\d+)")
# Only the programs that run the server; never a shell that merely typed the command.
SERVER_PROGRAMS = re.compile(r"^(uv|factordesk|python(\d+(\.\d+)?)?w?)(\.exe)?$", re.IGNORECASE)


def program_name(command_line: str) -> str:
    """The file name of the program in a command line, without quotes or folders."""
    text = command_line.strip()
    first = text[1:].split('"', 1)[0] if text.startswith('"') else text.split(None, 1)[0]
    return re.split(r"[\\/]", first)[-1] if first else ""


def serve_pids(port: int) -> set[int]:
    """Process ids whose command line is `factordesk serve` on this port.

    A fallback for when the port table does not list the server (some Windows security tools
    hide it). A command line without --port means the default port, 8000.
    """
    if sys.platform == "win32":
        command = (
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*factordesk*' }"
            ' | ForEach-Object { "$($_.ProcessId)`t$($_.CommandLine)" }'
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        rows = [line.split("\t", 1) for line in out.splitlines() if "\t" in line]
    else:
        out = subprocess.run(
            ["ps", "-eo", "pid=,args="], capture_output=True, text=True, check=False
        ).stdout
        rows = [line.strip().split(None, 1) for line in out.splitlines() if line.strip()]
    pids: set[int] = set()
    for row in rows:
        if len(row) != 2 or not row[0].strip().isdigit():
            continue
        if not SERVER_PROGRAMS.match(program_name(row[1])):
            continue
        match = SERVE.search(row[1])
        if match is None:
            continue
        flag = PORT_FLAG.search(match.group("rest"))
        if (int(flag.group(1)) if flag else 8000) == port:
            pids.add(int(row[0]))
    pids.discard(os.getpid())
    return pids


def stop(pid: int) -> None:
    if sys.platform == "win32":
        # /T also stops the processes it started (uv run starts Python as a child).
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)


def run_npm(args: list[str]) -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("error: npm was not found; install Node 26 or newer with npm 12 or newer.")
        return 2
    return subprocess.run([npm, *args], check=False).returncode


def stop_server(port: int) -> int:
    state = is_factordesk(port)
    if state is None:
        print(f"Nothing answers on port {port}; no server to stop.")
        return 0
    if state is False:
        print(f"error: port {port} is used by another program, not factordesk; nothing stopped.")
        return 1
    pids = listening_pids(port) or serve_pids(port)
    if not pids:
        print(f"error: factordesk answers on port {port}, but its process was not found.")
        print("Stop it with Ctrl+C in the window where it runs.")
        return 1
    for pid in sorted(pids):
        stop(pid)
    for _ in range(20):
        if is_factordesk(port) is None:
            print(f"Stopped the factordesk server on port {port}.")
            return 0
        time.sleep(0.25)
    print(f"error: the server on port {port} is still answering.")
    return 1


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "npm":
        return run_npm(sys.argv[2:])
    parser = argparse.ArgumentParser(description="Helpers for the shortcut tasks.")
    sub = parser.add_subparsers(dest="command", required=True)
    stop_parser = sub.add_parser("stop", help="stop the factordesk server on a port")
    stop_parser.add_argument("--port", type=int, default=8000, help="port the server listens on")
    sub.add_parser("npm", help="run npm with the remaining arguments")
    args = parser.parse_args()
    return stop_server(args.port)


if __name__ == "__main__":
    sys.exit(main())
