#!/usr/bin/env python3
"""
visio_ctl.py — CLI controller for visio-sentinel.

Designed for AI agents (Hermes, OpenClaw) and human operators.
Reads the same .env and skill file as the daemon — no separate state.

Usage:
  python visio_ctl.py status              # daemon running? last event?
  python visio_ctl.py events [N=10]       # last N events from the log
  python visio_ctl.py persons             # list known persons
  python visio_ctl.py add-person <name>   # add a known person to skill file
  python visio_ctl.py remove-person <name># remove a known person from skill file
  python visio_ctl.py start               # start daemon in background
  python visio_ctl.py stop                # stop daemon
  python visio_ctl.py tail                # stream events live
"""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent
_LOG_PATH = Path(os.getenv("LOG_PATH", str(_ROOT / "logs" / "events.jsonl")))
_SKILL_PATH = Path(os.getenv("SKILL_PATH", str(_ROOT / "agent" / "skills" / "home_security.md")))
_PID_FILE = _ROOT / ".visio_sentinel.pid"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _read_events(n: int) -> list[dict]:
    if not _LOG_PATH.exists():
        return []
    lines = _LOG_PATH.read_text().strip().splitlines()
    return [json.loads(l) for l in lines[-n:] if l.strip()]


def _read_known_persons() -> list[str]:
    if not _SKILL_PATH.exists():
        return []
    in_section = False
    persons: list[str] = []
    for line in _SKILL_PATH.read_text().splitlines():
        stripped = line.strip()
        if stripped == "## Known Persons":
            in_section = True
            continue
        if in_section:
            if stripped.startswith("##"):
                break
            if stripped.startswith("- "):
                persons.append(stripped[2:].strip())
    return persons


def _write_known_persons(persons: list[str]) -> None:
    text = _SKILL_PATH.read_text()
    section_re = re.compile(r"(## Known Persons\n)((?:- .+\n?)*)", re.MULTILINE)
    new_block = "## Known Persons\n" + "".join(f"- {p}\n" for p in persons)
    updated = section_re.sub(new_block, text)
    _SKILL_PATH.write_text(updated)


def _daemon_pid() -> int | None:
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, 0)  # signal 0 = existence check
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            _PID_FILE.unlink(missing_ok=True)
    return None


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_status() -> None:
    pid = _daemon_pid()
    if pid:
        print(f"daemon: RUNNING (pid {pid})")
    else:
        print("daemon: STOPPED")

    events = _read_events(1)
    if events:
        e = events[-1]
        print(
            f"last event: {e.get('ts')} | person={e.get('person')} "
            f"known={e.get('known')} conf={e.get('confidence', 0):.2f} "
            f"priority={e.get('priority')}"
        )
    else:
        print("last event: none (log empty or not found)")


def cmd_events(n: int) -> None:
    events = _read_events(n)
    if not events:
        print("No events found.")
        return
    for e in events:
        known_str = "known" if e.get("known") else "UNKNOWN"
        err = f" error={e['error']}" if e.get("error") else ""
        print(
            f"{e.get('ts')} [{e.get('priority'):8}] "
            f"{e.get('person')} ({known_str}) "
            f"conf={e.get('confidence', 0):.2f}{err}"
        )


def cmd_persons() -> None:
    persons = _read_known_persons()
    if not persons:
        print("No known persons configured.")
        return
    print("Known persons:")
    for p in persons:
        print(f"  - {p}")


def cmd_add_person(name: str) -> None:
    name = name.strip().lower()
    if not name:
        print("Error: name cannot be empty.")
        sys.exit(1)
    persons = _read_known_persons()
    if name in persons:
        print(f"'{name}' is already in the known persons list.")
        return
    persons.append(name)
    _write_known_persons(persons)
    print(f"Added '{name}' to known persons. Restart daemon to apply.")


def cmd_remove_person(name: str) -> None:
    name = name.strip().lower()
    persons = _read_known_persons()
    if name not in persons:
        print(f"'{name}' not found in known persons list.")
        return
    persons.remove(name)
    _write_known_persons(persons)
    print(f"Removed '{name}'. Restart daemon to apply.")


def cmd_start() -> None:
    if _daemon_pid():
        print("Daemon is already running.")
        return
    proc = subprocess.Popen(
        [sys.executable, str(_ROOT / "agent" / "agent.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _PID_FILE.write_text(str(proc.pid))
    print(f"Daemon started (pid {proc.pid}). Logs: {_LOG_PATH}")


def cmd_stop() -> None:
    pid = _daemon_pid()
    if not pid:
        print("Daemon is not running.")
        return
    os.kill(pid, signal.SIGTERM)
    _PID_FILE.unlink(missing_ok=True)
    print(f"Sent SIGTERM to pid {pid}.")


def cmd_tail() -> None:
    if not _LOG_PATH.exists():
        print(f"Log file not found: {_LOG_PATH}")
        sys.exit(1)
    print(f"Tailing {_LOG_PATH} (Ctrl-C to stop)\n")
    try:
        with _LOG_PATH.open() as f:
            f.seek(0, 2)  # seek to end
            while True:
                line = f.readline()
                if line:
                    try:
                        e = json.loads(line)
                        known_str = "known" if e.get("known") else "UNKNOWN"
                        err = f" error={e['error']}" if e.get("error") else ""
                        print(
                            f"{e.get('ts')} [{e.get('priority'):8}] "
                            f"{e.get('person')} ({known_str}) "
                            f"conf={e.get('confidence', 0):.2f}{err}"
                        )
                    except json.JSONDecodeError:
                        print(line.rstrip())
                else:
                    import time
                    time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "status":
        cmd_status()
    elif cmd == "events":
        n = int(args[1]) if len(args) > 1 else 10
        cmd_events(n)
    elif cmd == "persons":
        cmd_persons()
    elif cmd == "add-person":
        if len(args) < 2:
            print("Usage: visio_ctl.py add-person <name>")
            sys.exit(1)
        cmd_add_person(args[1])
    elif cmd == "remove-person":
        if len(args) < 2:
            print("Usage: visio_ctl.py remove-person <name>")
            sys.exit(1)
        cmd_remove_person(args[1])
    elif cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "tail":
        cmd_tail()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
