# Proposed skills and adoption text

Approval pending. This file is a review draft only. The five SKILL.md files and public adoption documentation below have not been installed or published. Proposed skill destinations are `skills/<name>/SKILL.md`. Each skill is intentionally self-contained; API details belong in the package's authoritative public reference.

## Proposed skill: skills/plan-behavioral-change/SKILL.md

```markdown
---
name: plan-behavioral-change
description: Plan an application behavior change around executable acceptance conditions and meaningful red/green evidence. Use before implementing a feature or changing an observable contract.
---

Inspect repository instructions, existing scenarios and coverage before choosing a new scenario, an extension or a narrower check. Describe the requested behavior through production entry points, permitted inputs, state transitions and important negative cases. Record unresolved specification questions before implementing assumptions.

Choose the smallest observations that distinguish success from failure: actual responses, persisted state and semantic application events with selected required fields. Identify real startup, isolated storage, dependencies, service availability and timing costs. Missing services must remain an explicit coverage limit; simulated application results are not full-stack evidence.

Write or update the project's implementation plan around an executable acceptance condition. Include the selected checks, expected meaningful red result, implementation steps, green rerun, evidence location, known limits and required project approvals. Follow the project's plan location and format.

For new behavior, implement the scenario first and run it against the real application. Confirm that its failure demonstrates the missing behavior; an import, setup or configuration failure is not useful red evidence. Implement the behavior, rerun the same acceptance condition and preserve the oracle through refactoring. Change an expectation only when the intended behavior itself has been revised and reviewed.

For already-working behavior, record a genuine green baseline. Clearly label wrong-expectation or other negative controls; do not present them as a real product defect or an implementation mutation. Plan broader checks according to project cadence. Respect authorization boundaries, including documentation approval rules.
```

## Proposed skill: skills/integrate-scenario-testing/SKILL.md

```markdown
---
name: integrate-scenario-testing
description: Adopt the scenario-harness pytest plugin in a consuming application with real application fixtures, observation bindings and explicit execution policy.
---

Read the installed package's public API reference and the consuming repository's test policy. Keep domain actions, application lifecycle and admission policy in the consumer; do not import another application's validation framework or recreate a separate runner.

Install scenario-harness in the application's isolated test environment. It includes pytest and pytest-xdist. Use the scenario_run fixture for run-owned state and artifacts. An ordinary app fixture depends on scenario_run, starts the actual application, binds its actual observation sink and finalizes the application through pytest. Keep setup failures visible and ensure partial startup can release acquired resources.

Map application events into the name/data/optional-metadata envelope at the sink boundary. Scenarios must observe events emitted by the application, not manufacture expected observations themselves. Assert selected semantic fields, using checkpoints and correlation identifiers to avoid matching unrelated operations. Register known secrets before emitting them to plugin-owned evidence; raw application files need their own policy.

Start adoption with a small real outcome plus an internal semantic observation. Configure protected mode with explicit local workers, initially `--scenario-mode protected -n 1 --max-worker-restart=1`. Use `--scenario-mode inprocess` for deliberate debugging and recognize its reduced crash protection. Installing the plugin alone must not activate unrelated tests.

Set an explicit plugin-owned artifact root, retain reports according to project policy and make CI preserve failure artifacts. Verify the installed distribution from outside its source tree. Prove additional worker safety before increasing concurrency. Do not claim remote-worker, descendant cleanup or hard-hang guarantees without evidence. Python package installation does not install agent skills.
```

## Proposed skill: skills/develop-behavioral-scenarios/SKILL.md

```markdown
---
name: develop-behavioral-scenarios
description: Implement or extend pytest scenarios that exercise real application behavior and develop a change through meaningful red/green/refactor evidence.
---

Inspect the behavior plan, neighboring scenarios and application fixture before writing a new case. Reuse the project's ordinary pytest app fixture and production entry points. Controlled inputs are allowed; mocked application outputs and private collaborator call assertions do not establish the behavior.

For a new behavior, write the smallest acceptance case first. Run it and explain why the observed failure discriminates the missing behavior from unrelated environment faults. Implement the production change and rerun the same case. Keep expected outcomes stable through refactoring. For working behavior under migration, use a real green baseline and label any negative controls honestly.

Assert actual output or persisted state and relevant application-emitted events through scenario_run.observations. Match semantic names and minimum required fields; tolerate unrelated metadata and additional fields. Use checkpoints and operation identifiers where necessary. Do not assert logger classes, complete event snapshots, timestamps or private call order unless these are explicitly the product contract.

Retain useful outputs with scenario_run.save_json or write_text, register explicit secrets before use, and keep raw files subject to project policy. Cover meaningful negative cases and cleanup. Run directly relevant deterministic checks during development and broader checks at the repository's designated hardening point. Report actual red/green results, evidence paths and remaining coverage limits.
```

## Proposed skill: skills/review-behavioral-scenarios/SKILL.md

```markdown
---
name: review-behavioral-scenarios
description: Review scenario changes for meaningful behavioral coverage, stable semantic assertions and trustworthy execution evidence.
---

Compare the requested contract, implementation and scenario diff. Determine whether real production entry points produce the asserted outputs, persisted state or observations. Trace event publication to the application sink; test-emitted expected events are not proof. Distinguish controlled input fixtures from substituted application outcomes.

Check whether the oracle rejects a plausible incorrect behavior. Reject weakened expectations that hide a failure without an explicitly revised behavior contract, even when tests become green. Prefer selected semantic fields over snapshots of metadata, internal classes or collaborator call order. Check correlations, timing assumptions, negative cases and isolation between reused workers.

Inspect actual pytest phase verdicts and artifacts, including setup and teardown failures. Verify that a claimed red result demonstrates missing behavior and that migration negative controls are labelled. Passing output alone cannot establish cleanup after a dead worker. Assess admission, live-service limits and broader-profile evidence against the consuming project's policy.

Report actionable findings with affected locations, the behavioral consequence and supporting evidence. Separate observed defects from coverage limits. Skills guide judgment; they neither grant approval nor mechanically certify test quality.
```

## Proposed skill: skills/diagnose-scenario-failures/SKILL.md

```markdown
---
name: diagnose-scenario-failures
description: Diagnose pytest scenario failures using phase reports, semantic observations and retained artifacts, including application startup errors, cleanup failures and worker loss.
---

Read pytest's verdict and the plugin's JSON/Markdown evidence together. Identify the earliest relevant setup, call or teardown failure, selected node, worker, exception and artifact directory. Preserve concurrent assertion and cleanup failures rather than treating one as the explanation for both.

Reproduce the smallest relevant case with isolated state and the same inputs. Keep protected mode when investigating worker behavior; use explicit in-process debugging only when needed and record the changed protection. Diagnose infrastructure failures separately from application behavior failures. Never weaken the expected behavior or silently substitute simulated application results to obtain green output.

Use checkpoints, correlation fields and application outputs to locate the last established state transition. Redact registered values in shared excerpts; raw application files may require separate handling. A process death has no Python exception object: distinguish genuine fatal diagnostics from missing evidence and mark cleanup unconfirmed unless established independently.

After a fault, verify a subsequent real application lifecycle when contamination or worker replacement matters. A deliberate failing probe should still exit nonzero; report recovery verification separately. Summarize the demonstrated cause, reproducer, evidence, fix verification and unresolved limits. Do not promise hard-hang or descendant-process cleanup without tested support.
```

## Proposed installation and usage text

The Python package and agent skills are installed separately. Install the tested package revision in your application's test environment; pytest and pytest-xdist are included dependencies. Copy whichever approved `skills/<name>` directories you need into `${CODEX_HOME:-$HOME/.codex}/skills/`. Each installed directory must contain its own SKILL.md. Installation must be an explicit user action; pip must not write agent configuration or skills into a home directory.

Invoke `$plan-behavioral-change` before implementing a behavior change, `$integrate-scenario-testing` when adopting the plugin, `$develop-behavioral-scenarios` while authoring cases, `$review-behavioral-scenarios` for review and `$diagnose-scenario-failures` for investigation. These skills remain automatically discoverable through their descriptions. They respect the consuming repository's instructions and approvals.

For editable sibling development, create a dedicated environment and install the sibling checkout with `python -m pip install -e ../scenario-harness`. Keep environments for incompatible published revisions separate. Production CI should install its tested immutable revision rather than rely on a sibling working tree.

The `examples/notes_app` consumer runs an actual local HTTP server with SQLite persistence. Its app fixture creates isolated state in scenario_run.root and binds production semantic events to scenario_run.observations.record. The scenarios perform real HTTP requests, retrieve persisted output and assert selected application event fields. They do not need an external service or an additional application framework dependency.

Run passing examples with `python -m pytest examples/notes_app --scenario-mode protected -n 1 --max-worker-restart=1 --scenario-root /tmp/notes-scenario-evidence`. The wrong-event negative control is skipped by default. To inspect a deliberate assertion failure, select `test_wrong_expected_event_demonstrates_failure` and add `--example-faults`; exit status 1 is the expected result of that probe. It demonstrates failure reporting and oracle discrimination, not a product implementation defect. In-process debugging uses `--scenario-mode inprocess` without `-n`.

For an installed-wheel check, copy `examples/notes_app` outside the repository, install the wheel in a clean environment, change to the copied directory and run `python -m pytest --scenario-mode protected -n 1 --max-worker-restart=1 --scenario-root <evidence-directory>`. This checks plugin discovery and a real consumer without source-path injection. Preserve the plugin reports and relevant application artifacts in CI. Register explicit secrets before plugin-owned output and separately govern raw application files.

## Validation still required before publication

Extract approved skills into their final destinations and run the skill creator's quick_validate.py against each package. Exercise realistic planning, authoring, review and diagnosis tasks in isolated consumer projects when authorized; metadata validation alone does not establish skill quality. In particular, verify that planning produces a meaningful executable red acceptance condition, review rejects a weakened oracle and diagnosis separates intentional failure from successful recovery. Public skill installation and publication remain pending explicit approval of this draft.
