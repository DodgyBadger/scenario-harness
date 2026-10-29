"""Real watchdog deaths clean inherited descendants before worker replacement."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_plugin import execute


def running(pid):
    path = Path(f"/proc/{pid}/stat")
    try:
        return path.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Linux ownership policy"
)
@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_watchdog_kills_hung_worker_and_owned_descendants_only(tmp_path, phase):
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        child_program = """import json, os, signal, subprocess, sys, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
grandchild = subprocess.Popen([sys.executable, '-c', 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'])
Path(sys.argv[1]).write_text(json.dumps([os.getpid(), grandchild.pid]))
time.sleep(60)
"""
        source = f"""
import json, os, subprocess, sys, threading, time
from pathlib import Path
import pytest
pytestmark = pytest.mark.timeout(0, method='signal', func_only=True)
@pytest.fixture
def owned(scenario_run):
    process = subprocess.Popen([sys.executable, '-c', {child_program!r}, str(Path.cwd() / 'owned.json')])
    while not Path('owned.json').exists():
        time.sleep(0.01)
    scenario_run.save_json('durable.json', {{'pid': os.getpid(), 'phase': {phase!r}}})
    if {phase!r} == 'setup':
        threading.Event().wait()
    yield
    if {phase!r} == 'teardown':
        threading.Event().wait()
def test_hang(owned):
    if {phase!r} == 'call':
        threading.Event().wait()
def test_next_healthy(scenario_run):
    for pid in json.loads(Path('owned.json').read_text()):
        path = Path(f'/proc/{{pid}}/stat')
        assert not path.exists() or path.read_text().rsplit(')',1)[1].split()[0] == 'Z'
    scenario_run.save_json('healthy.json', {{'ok': True}})
"""
        started = time.monotonic()
        result, report = execute(
            tmp_path,
            source,
            "--scenario-mode",
            "protected",
            "-n",
            "1",
            "--scenario-timeout",
            "2",
            "--timeout",
            "0",
            "--max-worker-restart",
            "1",
        )
        assert time.monotonic() - started < 25, result.stdout + result.stderr
        assert result.returncode == 1
        assert report["capabilities"]["hard_hang_timeout"] is False
        assert report["capabilities"]["worker_timeout_watchdog"] is True
        assert (
            "GIL-held native code unsupported"
            in report["capabilities"]["timeout_mechanism"]
        )
        assert (
            "detached sessions unsupported"
            in report["capabilities"]["process_cleanup_scope"]
        )
        assert (
            sentinel.poll() is None
        ), "Controller-owned unrelated process must survive"
        cases = {case["nodeid"].split("::")[-1]: case for case in report["tests"]}
        assert cases["test_hang"]["worker_crashed"]
        assert cases["test_hang"]["cleanup_status"] == "unconfirmed"
        assert cases["test_next_healthy"]["status"] == "passed"
        assert cases["test_hang"]["workers"] != cases["test_next_healthy"]["workers"]
        assert list((tmp_path / "evidence/workers").rglob("durable.json"))
        cleanup = [
            event
            for event in report["worker_events"]
            if event["event"] == "worker_process_cleanup"
            and event["worker"] == cases["test_hang"]["workers"][0]
        ]
        assert len(cleanup) == 1 and cleanup[0]["status"] == "completed"
        assert len(cleanup[0]["owned_pids"]) >= 2
        assert all(
            not running(pid)
            for pid in json.loads((tmp_path / "owned.json").read_text())
        )
    finally:
        sentinel.kill()
        sentinel.wait(timeout=5)
        if (tmp_path / "owned.json").exists():
            import os
            import signal

            for pid in json.loads((tmp_path / "owned.json").read_text()):
                if running(pid):
                    os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_protected_watchdog_rejects_disabled_or_unbounded_deadline(tmp_path, value):
    result, _ = execute(
        tmp_path,
        "def test_ok(): pass",
        "--scenario-mode",
        "protected",
        "-n",
        "1",
        "--scenario-timeout",
        value,
    )
    assert result.returncode == 4
    assert "finite and positive" in result.stderr
