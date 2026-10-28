import json
import os
import subprocess
import sys

import pytest

from scenario_harness import ScenarioRun


def test_observations_and_artifacts(tmp_path):
    run = ScenarioRun(tmp_path)
    run.register_secret("secret-value")
    run.observations.record(
        "ready", {"nested": {"ok": True, "extra": 3}, "credential": "secret-value"}
    )
    checkpoint = run.observations.checkpoint()
    assert (
        run.observations.require("ready", nested={"ok": True})["data"]["nested"][
            "extra"
        ]
        == 3
    )
    assert not run.observations.contains("ready", after=checkpoint)
    with pytest.raises(AssertionError):
        run.observations.require("ready", nested={"ok": False})
    assert "secret-value" not in (run.artifacts / "observations.jsonl").read_text()
    with pytest.raises(ValueError):
        run.save_json("../escape", {})


def execute(tmp_path, source, *options):
    (tmp_path / "test_app.py").write_text(source)
    env = {**os.environ, "PYTHONFAULTHANDLER": "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tmp_path / "test_app.py"),
            "--scenario-root",
            str(tmp_path / "evidence"),
            "--junitxml",
            str(tmp_path / "junit.xml"),
            *options,
        ],
        check=False,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    path = tmp_path / "evidence/report.json"
    return result, json.loads(path.read_text()) if path.exists() else None


@pytest.mark.parametrize("workers", [0, 1, 2])
def test_sync_async_outcomes(tmp_path, workers):
    result, report = execute(
        tmp_path,
        """import pytest
import asyncio

def test_sync(scenario_run):
    scenario_run.record('ready', {'ok': True, 'extra': 5})
    scenario_run.observations.require('ready', ok=True)

@pytest.mark.asyncio
async def test_async(scenario_run):
    await asyncio.sleep(0)
    scenario_run.save_json('output.json', {'ok': True})

@pytest.mark.skip(reason='unavailable')
def test_skip(): pass

@pytest.mark.xfail(reason='known')
def test_xfail(): assert False

@pytest.mark.xfail(reason='resolved')
def test_xpass(): pass
""",
        "--scenario-mode",
        "protected" if workers else "inprocess",
        "-n",
        str(workers),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(t["status"] for t in report["tests"]) == [
        "passed",
        "passed",
        "skipped",
        "xfailed",
        "xpassed",
    ]
    assert all(t["cleanup_status"] == "completed" for t in report["tests"])
    assert len({t["evidence_path"] for t in report["tests"]}) == 5


def test_failure_teardown_and_redaction(tmp_path):
    result, report = execute(
        tmp_path,
        """import pytest
@pytest.fixture
def app(scenario_run):
    scenario_run.register_secret('credential-SENSITIVE')
    yield
    raise RuntimeError('cleanup credential-SENSITIVE')
def test_fault(app):
    print('captured credential-SENSITIVE')
    raise ValueError('execution credential-SENSITIVE')
""",
        "--scenario-mode",
        "protected",
        "-n",
        "1",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    case = report["tests"][0]
    assert case["status"] == "failed"
    assert case["cleanup_status"] == "failed"
    assert [p["exception"]["type"] for p in case["phases"] if p["exception"]] == [
        "builtins.ValueError",
        "builtins.RuntimeError",
    ]
    assert "credential-SENSITIVE" not in result.stdout + result.stderr
    for path in [
        tmp_path / "junit.xml",
        *list((tmp_path / "evidence").rglob("*.json")),
        *list((tmp_path / "evidence").rglob("*.md")),
    ]:
        assert "credential-SENSITIVE" not in path.read_text(), path


def test_abort_replacement(tmp_path):
    result, report = execute(
        tmp_path,
        """import os
import faulthandler
def test_abort(scenario_run):
    scenario_run.save_json('durable.json', {'before': 'abort'})
    with (scenario_run.artifacts / 'fatal-stack.txt').open('w') as stream:
        faulthandler.enable(stream)
        os.abort()
def test_recovered(scenario_run):
    scenario_run.record('recovered', {'ok': True})
""",
        "--scenario-mode",
        "protected",
        "-n",
        "1",
        "--max-worker-restart",
        "1",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    cases = {t["nodeid"].split("::")[-1]: t for t in report["tests"]}
    assert cases["test_abort"]["status"] == "failed"
    assert cases["test_abort"]["worker_crashed"]
    assert cases["test_abort"]["fatal_stack_path"]
    assert cases["test_abort"]["phases"][-1]["exception"] is None
    assert cases["test_abort"]["cleanup_status"] == "unconfirmed"
    assert cases["test_recovered"]["status"] == "passed"
    assert list((tmp_path / "evidence/workers").rglob("durable.json"))
    assert (
        len([e for e in report["worker_events"] if e["event"] == "worker_created"]) == 2
    )


def test_explicit_activation(tmp_path):
    result, report = execute(
        tmp_path, "def test_ok(): pass", "--scenario-mode", "protected"
    )
    assert result.returncode == 4
    assert report is None


def test_setup_error_then_reused_worker(tmp_path):
    result, report = execute(
        tmp_path,
        """import pytest
@pytest.fixture
def broken(): raise LookupError('startup invalid')
def test_startup(broken): pass
def test_next(scenario_run): scenario_run.record('healthy')
""",
        "--scenario-mode",
        "protected",
        "-n",
        "1",
    )
    assert result.returncode == 1
    first, second = report["tests"]
    assert first["status"] == "failed"
    assert first["phases"][0]["exception"]["type"] == "builtins.LookupError"
    assert second["status"] == "passed"
    assert first["workers"] == second["workers"] == ["gw0"]


def test_unstarted_cases_are_retained(tmp_path):
    result, report = execute(
        tmp_path,
        """def test_first(): assert False
def test_unstarted(): pass
""",
        "--scenario-mode",
        "inprocess",
        "-x",
    )
    assert result.returncode == 1
    assert [t["status"] for t in report["tests"]] == ["failed", "incomplete"]
    assert report["tests"][1]["cleanup_status"] == "unconfirmed"


def test_inert_and_existing_evidence_protection(tmp_path):
    result, report = execute(tmp_path, "def test_regular(): pass")
    assert result.returncode == 0
    assert report is None
    (tmp_path / "evidence").mkdir()
    sentinel = tmp_path / "evidence/retained.txt"
    sentinel.write_text("retain me")
    result, report = execute(
        tmp_path, "def test_regular(): pass", "--scenario-mode", "inprocess"
    )
    assert result.returncode == 4
    assert sentinel.read_text() == "retain me"


def test_actual_verdict_overrides_metadata(tmp_path):
    (tmp_path / "conftest.py").write_text("""import pytest
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):
    # Deliberately forged transport metadata cannot change pytest's verdict.
    report.user_properties.append(('scenario_phase', {'phase': 'call', 'outcome': 'passed', 'duration': 0, 'exception': None}))
""")
    result, report = execute(
        tmp_path, "def test_failure(): assert False", "--scenario-mode", "inprocess"
    )
    assert result.returncode == 1
    assert report["tests"][0]["status"] == "failed"
    assert report["tests"][0]["phases"][1]["outcome"] == "failed"


def test_collection_failure_recorded(tmp_path):
    result, report = execute(
        tmp_path, "raise RuntimeError('invalid import')", "--scenario-mode", "inprocess"
    )
    assert result.returncode == 2
    assert report["collection_errors"]
    assert "invalid import" in report["collection_errors"][0]["traceback"]


def test_dist_each_rejected(tmp_path):
    result, report = execute(
        tmp_path,
        "def test_ok(): pass",
        "--scenario-mode",
        "protected",
        "-n",
        "2",
        "--dist=each",
    )
    assert result.returncode == 4
    assert report is None


def test_xfail_reason_redaction(tmp_path):
    result, report = execute(
        tmp_path,
        """import pytest
def test_xfail(scenario_run):
    scenario_run.register_secret('sensitive-xfail-reason')
    pytest.xfail('sensitive-xfail-reason')
""",
        "--scenario-mode",
        "protected",
        "-n",
        "1",
    )
    assert result.returncode == 0
    assert report["tests"][0]["status"] == "xfailed"
    for path in [
        tmp_path / "junit.xml",
        tmp_path / "evidence/report.json",
        tmp_path / "evidence/report.md",
    ]:
        assert "sensitive-xfail-reason" not in path.read_text()


def test_secret_event_expectation(tmp_path):
    run = ScenarioRun(tmp_path)
    run.register_secret("secret-value")
    run.record("authenticated", {"token": "secret-value"})
    run.observations.require("authenticated", token="secret-value")


def test_crash_during_setup_links_durable_evidence(tmp_path):
    result, report = execute(
        tmp_path,
        """import os
import pytest
@pytest.fixture
def app(scenario_run):
    scenario_run.save_json('startup.json', {'starting': True})
    os._exit(23)
def test_crash(app): pass
def test_after(scenario_run): pass
""",
        "--scenario-mode",
        "protected",
        "-n",
        "1",
        "--max-worker-restart",
        "1",
    )
    assert result.returncode == 1
    case = next(t for t in report["tests"] if t["nodeid"].endswith("::test_crash"))
    assert case["worker_crashed"]
    assert case["cleanup_status"] == "unconfirmed"
    from pathlib import Path

    assert (Path(case["evidence_path"]) / "artifacts/startup.json").is_file()
    assert case["fatal_stack_path"] is None


def test_long_parameter_ids_keep_artifact_paths_bounded(tmp_path):
    from scenario_harness.plugin import RunEvidence

    state = RunEvidence(tmp_path)
    first = state.evidence("test_app.py::test_case[" + "x" * 1000 + "]")
    second = state.evidence("test_app.py::test_case[" + "x" * 999 + "y]")
    assert len(first.root.name) <= 91
    assert first.root != second.root
    assert first.artifacts.is_dir()
