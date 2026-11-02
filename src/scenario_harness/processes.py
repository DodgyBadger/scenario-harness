"""Bounded cleanup of inherited Linux worker sessions; never caller groups."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path


def process_identity(pid: int) -> dict:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {
        "pid": pid,
        "state": fields[0],
        "pgid": int(fields[2]),
        "sid": int(fields[3]),
        "start_time": fields[19],
    }


def claim_worker_session() -> dict:
    os.setsid()
    identity = process_identity(os.getpid())
    if identity["pgid"] != identity["pid"] or identity["sid"] != identity["pid"]:
        raise RuntimeError("Could not establish an exclusive scenario worker session")
    return identity


def cleanup_worker_session(identity: dict, *, grace: float = 0.3) -> dict:
    pid = identity["pid"]
    if (
        pid <= 1
        or identity["pgid"] != pid
        or identity["sid"] != pid
        or pid in {os.getpid(), os.getpgrp(), os.getsid(0)}
    ):
        return {"status": "unconfirmed", "reason": "unsafe_worker_identity"}
    try:
        current = process_identity(pid)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as error:
        return {"status": "unconfirmed", "reason": type(error).__name__}
    else:
        if current["start_time"] != identity["start_time"]:
            return {"status": "unconfirmed", "reason": "worker_pid_reused"}

    def members():
        found = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                member = process_identity(int(entry.name))
            except (FileNotFoundError, ProcessLookupError):
                continue
            if member["sid"] == pid and member["state"] != "Z":
                found.append(member)
        return found

    try:
        initial = members()
        for signum in (signal.SIGTERM, signal.SIGKILL):
            remaining = members()
            if not remaining:
                break
            # Every group is discovered inside the verified worker session. A
            # child may create another group, but another session is unsupported.
            for pgid in {member["pgid"] for member in remaining}:
                if pgid <= 1 or pgid == os.getpgrp():
                    return {
                        "status": "unconfirmed",
                        "reason": "unsafe_descendant_group",
                    }
                try:
                    os.killpg(pgid, signum)
                except ProcessLookupError:
                    pass
            deadline = time.monotonic() + grace
            while time.monotonic() < deadline and members():
                time.sleep(0.01)
        remaining = members()
        return {
            "status": "completed" if not remaining else "unconfirmed",
            "owned_pids": [member["pid"] for member in initial],
            "remaining_pids": [member["pid"] for member in remaining],
            "scope": "inherited_worker_session; detached_sessions_not_owned",
        }
    except (OSError, ValueError) as error:
        return {"status": "unconfirmed", "reason": type(error).__name__}
