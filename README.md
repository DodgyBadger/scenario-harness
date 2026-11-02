# scenario-harness

A pytest plugin and agent skills for testing application behavior through real outputs and semantic observations. Pytest owns fixtures, execution and assertions; this package adds inspectable per-scenario evidence and protected worker execution.

## Install and run

Install the tested package revision in your application's test environment. For sibling development, use `uv pip install -e ../scenario-harness`; CI should install an immutable tested revision. The package includes pytest, pytest-xdist and pytest-timeout. Install application-specific test dependencies separately.

Write ordinary pytest scenarios and a fixture that starts your real application with isolated state under `scenario_run.root`. The fixture owns application shutdown. Use `scenario_run.save_json(name, value)` and `scenario_run.write_text(name, text)` for retained outputs. Bind application-produced semantic observations to `scenario_run.observations.record(name, data)` when output alone cannot establish an important behavior; the application chooses how to expose those observations.

```python
def test_saved_note(app, scenario_run):
    app.save_note("Travel", "Bring passport")
    assert app.read_note("Travel") == "Bring passport"
    scenario_run.save_json("saved-note.json", {"text": app.read_note("Travel")})
```

The `app` fixture above belongs to the consuming project and must call its real application. See the runnable HTTP/SQLite application and fixture in [examples/notes_app](examples/notes_app).

```bash
python -m pytest examples/notes_app --scenario-mode protected -n 1 --max-worker-restart=1 --scenario-timeout 300 --scenario-root /tmp/notes-evidence
```

Choose an empty evidence directory for each invocation. Reports are written to `report.json` and `report.md`; individual cases retain phase reports, observations and artifacts. Register known secrets before retaining plugin-owned evidence. Raw application files need their own logging and retention policy.

Protected mode requires local Linux workers and `/proc`. The controller enforces the whole-item deadline, including native calls that hold a worker's GIL; the worker also has a pytest-timeout watchdog. After worker death, inherited processes in the verified worker session are cleaned up before replacement. Deliberately detached sessions are unsupported. Process cleanup does not establish that the killed application's finalizers ran: application cleanup remains unconfirmed. Collection/startup hangs before an item begins need an outer CI/job timeout. This plugin is not an OS network or filesystem sandbox. For deliberate debugging, use `--scenario-mode inprocess -n 0` with reduced crash protection.

## What may be mocked

Keep in-app services real. Do not replace application strategies, collaborators, persistence or evidence producers with expected outcomes. Test behavior through production entry points and let the actual application produce its responses, files, state and observations.

External services and environmental dependencies may be simulated when live calls are impractical, slow, variable, costly or require secrets. For example, a fixture can supply provider HTTP responses or DNS answers while the application's policy, orchestration, parsing and persistence remain real. A temporary local server is useful when real protocol behavior matters; it is not mandatory for every provider test.

Document each substitution beside its fixture or test: what is replaced, why, what remains real and what is unproven. Do not substitute an in-app service merely because it makes a failure easier to avoid. Simulated external responses prove application behavior under those inputs, not that the live provider works. Keep a small optional live compatibility check where that distinction matters.

## Browser scenarios

Use Playwright's maintained pytest integration in the consuming application; scenario-harness does not require Playwright or manage browser automation. Shared application fixtures should serve the actual app on a loopback HTTP port, own isolated state and define browser/network policy. Scenarios consume those fixtures and assert user journeys through the real UI/backend. Keep browser configuration and loop scopes separate from non-browser profiles where their lifecycle requirements differ.

Save screenshots and trace ZIPs directly under `scenario_run.artifacts`, and retain console/page/request diagnostics with `scenario_run.save_json`. Browser diagnostics must be exported before closing their context; attempt trace export even if screenshot capture fails. These binary files are retained as produced and are not scrubbed by the plugin's JSON/text redactor, so use synthetic test data and credentials. Keep browser context/listener cleanup evidence separate from the fact that pytest finalizers returned. Existing worker deadlines do not establish cleanup of deliberately detached browser processes after forced worker death.

## Agent skills

Skills are separate from Python package installation. Copy the selected directories from [skills](skills) into your agent's configured skills directory explicitly; installing the package does not modify agent configuration.

- [Plan behavioral changes](skills/plan-behavioral-change/SKILL.md): executable acceptance conditions and meaningful red/green evidence.
- [Integrate scenario testing](skills/integrate-scenario-testing/SKILL.md): application-owned fixtures and plugin adoption.
- [Test application behavior](skills/test-application-behavior/SKILL.md): the methodology, readable scenarios and external-dependency boundaries.
- [Review scenarios](skills/review-behavioral-scenarios/SKILL.md): meaningful oracles and trustworthy evidence.
- [Diagnose failures](skills/diagnose-scenario-failures/SKILL.md): phase reports, retained failures and honest recovery claims.
