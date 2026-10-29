"""Small pytest reporting extension; pytest owns collection and execution."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import tempfile
import sys
from collections.abc import Generator
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from .context import ScenarioRun
from .processes import claim_worker_session, cleanup_worker_session, process_identity

_STATE: pytest.StashKey[RunEvidence] = pytest.StashKey()


Evidence = ScenarioRun


@dataclass
class RunEvidence:
    root: Path
    items: dict[str, Evidence] = field(default_factory=dict)
    reports: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    is_worker: bool = False
    external_paths: dict[str, str] = field(default_factory=dict)
    worker_events: list[dict[str, Any]] = field(default_factory=list)
    collection_errors: list[dict[str, Any]] = field(default_factory=list)
    worker_ownership: dict[str, dict[str, Any]] = field(default_factory=dict)

    def worker_event(self, event: str, worker: str, **details: Any) -> None:
        record = {"event": event, "worker": worker, **details}
        self.worker_events.append(record)
        with (self.root / "worker-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, default=str) + "\n")

    def evidence(self, nodeid: str) -> Evidence:
        if nodeid not in self.items:
            label = re.sub(r"[^A-Za-z0-9_-]", "_", nodeid.split("::")[-1])
            digest = hashlib.sha256(nodeid.encode()).hexdigest()[:10]
            item = Evidence(self.root / f"{label[:80]}-{digest}")
            item.artifacts.mkdir(parents=True, exist_ok=True)
            self.items[nodeid] = item
        return self.items[nodeid]


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("scenario-harness")
    group.addoption("--scenario-mode", choices=["protected", "inprocess"], default=None)
    group.addoption("--scenario-root", default=None)
    group.addoption(
        "--scenario-timeout",
        type=float,
        default=300.0,
        help="Protected per-item watchdog including setup and teardown (seconds)",
    )
    parser.addini(
        "scenario_mode", "protected or inprocess; empty disables evidence", default=""
    )
    parser.addini("scenario_root", "Empty directory for scenario evidence", default="")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "scenario: application behavioral scenario")
    mode = config.getoption("scenario_mode") or config.getini("scenario_mode")
    config._scenario_mode = mode
    if not mode:
        return
    if mode not in {"protected", "inprocess"}:
        raise pytest.UsageError("scenario_mode must be protected or inprocess")
    if mode == "protected":
        config.option.timeout_disable_debugger_detection = True
        import math

        seconds = config.getoption("scenario_timeout")
        if not math.isfinite(seconds) or seconds <= 0:
            raise pytest.UsageError(
                "protected --scenario-timeout must be finite and positive"
            )
        if not sys.platform.startswith("linux") or not Path("/proc/self/stat").exists():
            raise pytest.UsageError(
                "protected process ownership requires Linux /proc; use inprocess for unsupported platforms"
            )
        if not config.pluginmanager.hasplugin("timeout"):
            raise pytest.UsageError("protected mode requires pytest-timeout")
    workers = config.getoption("numprocesses", default=0)
    if (
        mode == "protected"
        and not getattr(config, "workerinput", None)
        and (not isinstance(workers, int) or workers < 1)
    ):
        raise pytest.UsageError(
            "protected scenario mode requires explicit -n N (N > 0)"
        )
    if mode == "inprocess" and workers:
        raise pytest.UsageError("inprocess scenario mode requires -n 0")
    if (
        any(
            "popen" not in tx or "//" in tx for tx in config.getoption("tx", default=[])
        )
        or config.getoption("dist", default="no") == "each"
    ):
        raise pytest.UsageError(
            "Scenario evidence supports local workers without --dist=each only"
        )
    config.pluginmanager.register(ReportCollector(config), "scenario-report-collector")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    if not session.config._scenario_mode:
        return
    worker_input = getattr(session.config, "workerinput", None)
    if worker_input is not None:
        root = (
            Path(worker_input["scenario_evidence_root"])
            / "workers"
            / worker_input["workerid"]
        )
        root.mkdir(parents=True)
        session.config.stash[_STATE] = RunEvidence(root, is_worker=True)
        if session.config._scenario_mode == "protected":
            try:
                identity = claim_worker_session()
                (root / "process-ownership.json").write_text(json.dumps(identity))
            except Exception as error:
                raise pytest.UsageError(
                    "Protected worker process ownership could not be established"
                ) from error
        return
    configured = session.config.getoption("scenario_root") or session.config.getini(
        "scenario_root"
    )
    root = (
        Path(configured).resolve()
        if configured
        else Path(tempfile.mkdtemp(prefix="scenario-harness-"))
    )
    if root.exists() and any(root.iterdir()):
        raise pytest.UsageError("--scenario-root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    session.config.stash[_STATE] = RunEvidence(root)


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node: Any) -> None:
    if _STATE not in node.config.stash:
        return
    state = node.config.stash[_STATE]
    node.workerinput["scenario_evidence_root"] = str(state.root)
    state.worker_event("worker_created", node.gateway.id)


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node: Any, ids: list[str]) -> None:
    if _STATE not in node.config.stash:
        return
    state = node.config.stash[_STATE]
    for nodeid in ids:
        state.evidence(nodeid)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodeready(node: Any) -> None:
    if _STATE not in node.config.stash or node.config._scenario_mode != "protected":
        return
    state = node.config.stash[_STATE]
    identity = json.loads(
        (
            state.root / "workers" / node.gateway.id / "process-ownership.json"
        ).read_text()
    )
    if process_identity(identity["pid"])["start_time"] != identity["start_time"]:
        raise pytest.UsageError(
            "Worker process ownership identity changed before readiness"
        )
    state.worker_ownership[node.gateway.id] = identity
    state.worker_event("worker_process_owned", node.gateway.id, **identity)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: Any, error: Any) -> None:
    if _STATE not in node.config.stash:
        return
    state = node.config.stash[_STATE]
    state.worker_event(
        "worker_down", node.gateway.id, error=str(error) if error else None
    )
    if node.config._scenario_mode == "protected":
        identity = state.worker_ownership.get(node.gateway.id)
        cleanup = (
            cleanup_worker_session(identity)
            if identity
            else {"status": "unconfirmed", "reason": "ownership_not_established"}
        )
        state.worker_event("worker_process_cleanup", node.gateway.id, **cleanup)
        if cleanup["status"] != "completed":
            node.config._scenario_cleanup_unconfirmed = True


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config._scenario_mode == "protected":
        for item in items:
            # Closest marker wins. Neither timeout(0), signal methods nor
            # func_only markers may disable the protected whole-item watchdog.
            item.add_marker(
                pytest.mark.timeout(
                    config.getoption("scenario_timeout"),
                    method="thread",
                    func_only=False,
                ),
                append=False,
            )


def pytest_collection_finish(session: pytest.Session) -> None:
    if _STATE not in session.config.stash:
        return
    # Selection hooks have finished; deselected cases are not incomplete runs.
    for item in session.items:
        session.config.stash[_STATE].evidence(item.nodeid)


@pytest.fixture
def scenario_run(request: pytest.FixtureRequest) -> Evidence:
    if _STATE not in request.config.stash:
        raise pytest.UsageError(
            "scenario_run requires explicit scenario_mode configuration"
        )
    run = request.config.stash[_STATE].evidence(request.node.nodeid)
    run.save_json(
        "ownership.json",
        {
            "nodeid": request.node.nodeid,
            "worker": getattr(request.config, "workerinput", {}).get(
                "workerid", "main"
            ),
            "pid": os.getpid(),
        },
    )
    return run


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[Any]
) -> Generator[None, Any]:
    outcome = yield
    report = outcome.get_result()
    if _STATE not in item.config.stash:
        return
    state = item.config.stash[_STATE]
    evidence = state.evidence(item.nodeid)
    phase = {
        "exception": (
            {
                "type": f"{type(call.excinfo.value).__module__}.{type(call.excinfo.value).__qualname__}",
                "summary": call.excinfo.exconly(),
            }
            if call.excinfo is not None
            else None
        ),
        "phase": report.when,
        "outcome": report.outcome,
        "duration": report.duration,
        "traceback": str(report.longrepr) if report.longrepr else None,
        "captures": [
            {"name": name, "text": content} for name, content in report.sections
        ],
    }
    # Scrub the actual forwarded report, including the JUnit and terminal boundaries.
    if report.longrepr:
        if isinstance(report.longrepr, tuple):
            report.longrepr = tuple(evidence.redact(v) for v in report.longrepr)
        elif evidence.redact(str(report.longrepr)) != str(report.longrepr):
            report.longrepr = evidence.redact(str(report.longrepr))
    report.sections = [
        (evidence.redact(k), evidence.redact(v)) for k, v in report.sections
    ]
    report.user_properties = [
        (evidence.redact(k), evidence.redact(v)) for k, v in report.user_properties
    ]
    if hasattr(report, "wasxfail"):
        report.wasxfail = evidence.redact(report.wasxfail)
    phase["wasxfail"] = evidence.redact(getattr(report, "wasxfail", None))
    phase["pid"] = os.getpid()
    phase["worker"] = getattr(item.config, "workerinput", {}).get("workerid", "main")
    report.user_properties.extend(
        [
            ("scenario_phase", evidence.redact(phase)),
            ("scenario_evidence_path", str(evidence.root)),
        ]
    )


class ReportCollector:
    def __init__(self, config: pytest.Config) -> None:
        self.config = config

    @pytest.hookimpl(optionalhook=True)
    def pytest_handlecrashitem(self, crashitem: str, report: pytest.TestReport) -> None:
        report.user_properties.append(("scenario_worker_crash", True))
        node = getattr(report, "node", None)
        if node is not None:
            report.user_properties.append(("scenario_worker_id", node.gateway.id))

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.config.stash[_STATE].collection_errors.append(
                {"nodeid": report.nodeid, "traceback": str(report.longrepr)}
            )

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        state = self.config.stash[_STATE]
        evidence = state.evidence(report.nodeid)
        properties = dict(report.user_properties)
        path = properties.get("scenario_evidence_path")
        if isinstance(path, str):
            state.external_paths[report.nodeid] = path
        transported_phase = properties.get("scenario_phase")
        phase: dict[str, Any]
        if isinstance(transported_phase, dict):
            phase = dict(transported_phase)
        else:
            phase = {
                "exception": None,
                "phase": (
                    "worker" if properties.get("scenario_worker_crash") else report.when
                ),
                "outcome": report.outcome,
                "duration": report.duration,
                "traceback": str(report.longrepr) if report.longrepr else None,
                "captures": [
                    {"name": name, "text": text} for name, text in report.sections
                ],
            }
        phase = {
            **phase,
            "phase": (
                "worker" if properties.get("scenario_worker_crash") else report.when
            ),
            "outcome": report.outcome,
            "duration": report.duration,
            "traceback": str(report.longrepr) if report.longrepr else None,
            "captures": [
                {"name": name, "text": text} for name, text in report.sections
            ],
            "wasxfail": getattr(report, "wasxfail", None),
            "worker_crash": bool(properties.get("scenario_worker_crash")),
        }
        if properties.get("scenario_worker_id"):
            phase["worker"] = properties["scenario_worker_id"]
        state.reports.setdefault(report.nodeid, []).append(evidence.redact(phase))
        evidence.save("pytest-phases.json", state.reports[report.nodeid])
        evidence.step("pytest_phase", phase=phase["phase"], outcome=phase["outcome"])


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _STATE not in session.config.stash:
        return
    state = session.config.stash[_STATE]
    if (
        getattr(session.config, "_scenario_cleanup_unconfirmed", False)
        and exitstatus == pytest.ExitCode.OK
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        exitstatus = session.exitstatus
    if state.is_worker:
        return
    tests = []
    lines = ["# Scenario evidence", "", f"Exit status: {int(exitstatus)}", ""]
    for nodeid, evidence in state.items.items():
        phases = state.reports.get(nodeid, [])
        skipped = next((p for p in phases if p["outcome"] == "skipped"), None)
        status = (
            "failed"
            if any(p["outcome"] == "failed" for p in phases)
            else (
                "passed"
                if any(
                    p["phase"] == "call" and p["outcome"] == "passed" for p in phases
                )
                and any(
                    p["phase"] == "teardown" and p["outcome"] == "passed"
                    for p in phases
                )
                else "incomplete"
            )
        )
        if status != "failed" and skipped:
            status = "xfailed" if skipped.get("wasxfail") else "skipped"
        elif status == "passed" and any(p.get("wasxfail") for p in phases):
            status = "xpassed"
        crashed = any(phase.get("worker_crash") for phase in phases)
        owned = list(
            (state.root / "workers").glob(
                f"*/{evidence.root.name}/artifacts/ownership.json"
            )
        )
        fallback = str(owned[0].parent.parent) if owned else str(evidence.root)
        evidence_path = state.external_paths.get(nodeid, fallback)
        fatal_stack = Path(evidence_path) / "artifacts/fatal-stack.txt"
        cleanup_status = (
            "unconfirmed"
            if crashed
            else (
                "completed"
                if any(
                    phase["phase"] == "teardown" and phase["outcome"] == "passed"
                    for phase in phases
                )
                else (
                    "failed"
                    if any(
                        p["phase"] == "teardown" and p["outcome"] == "failed"
                        for p in phases
                    )
                    else "unconfirmed"
                )
            )
        )
        tests.append(
            {
                "nodeid": nodeid,
                "status": status,
                "evidence_path": evidence_path,
                "controller_evidence_path": str(evidence.root),
                "worker_crashed": crashed,
                "workers": sorted({p.get("worker", "unknown") for p in phases}),
                "cleanup_status": cleanup_status,
                "fatal_stack_path": str(fatal_stack) if fatal_stack.exists() else None,
                "phases": phases,
            }
        )
        lines.extend(
            [
                f"## {nodeid}",
                "",
                f"Result: **{status}**",
                f"Cleanup: **{cleanup_status}**",
                f"Evidence: [{Path(evidence_path).name}]({Path(evidence_path).relative_to(state.root).as_posix()}/artifacts/)",
                "",
            ]
        )
        if fatal_stack.exists():
            lines.extend(
                [
                    f"Fatal-signal stack: [fatal-stack.txt]({fatal_stack.relative_to(state.root).as_posix()})",
                    "",
                ]
            )
        for phase in phases:
            lines.append(
                f"- {phase['phase']}: {phase['outcome']} ({phase['duration']:.3f}s)"
            )
            if phase["traceback"]:
                lines.extend(["", "```text", phase["traceback"], "```", ""])
        lines.append("")
    payload = {
        "schema": "scenario-harness.pytest/v1",
        "mode": session.config._scenario_mode,
        "capabilities": {
            "worker_crash_detection": session.config._scenario_mode == "protected",
            "hard_hang_timeout": False,
            "worker_timeout_watchdog": session.config._scenario_mode == "protected",
            "timeout_mechanism": "pytest-timeout thread watchdog; GIL-held native code unsupported",
            "timeout_seconds": (
                session.config.getoption("scenario_timeout")
                if session.config._scenario_mode == "protected"
                else None
            ),
            "descendant_process_cleanup": session.config._scenario_mode == "protected",
            "process_cleanup_scope": "verified inherited Linux worker sessions; detached sessions unsupported",
            "remote_workers": False,
        },
        "schema_version": 1,
        "exit_status": int(exitstatus),
        "versions": {
            "python": platform.python_version(),
            "pytest": pytest.__version__,
            "pytest-xdist": version("pytest-xdist"),
            "scenario-harness": version("scenario-harness"),
        },
        "collection_errors": state.collection_errors,
        "tests": tests,
        "worker_events": state.worker_events,
    }
    for error in state.collection_errors:
        lines.extend(
            [
                "## Collection error",
                "",
                error["nodeid"],
                "",
                "```text",
                error["traceback"],
                "```",
                "",
            ]
        )
    (state.root / "report.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (state.root / "report.md").write_text("\n".join(lines), encoding="utf-8")


def pytest_terminal_summary(terminalreporter: Any) -> None:
    if _STATE not in terminalreporter.config.stash:
        return
    state = terminalreporter.config.stash[_STATE]
    if state.is_worker:
        return
    root = state.root
    terminalreporter.write_sep("=", f"Scenario evidence: {root / 'report.md'}")
