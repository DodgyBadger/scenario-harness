# Scenario-harness pytest plugin and skills implementation plan

## Status and direction

Implementation underway. The user has chosen a lighter pytest plugin/library plus agent skills and documentation. The existing standalone engine has been replaced on dev/pytest-plugin-redesign; preserving its runner, CLI, project model or scenario inheritance API is not a goal. The earlier documentation-implementation-plan.md contains historical exploration and does not define the target architecture.

## Implementation checkpoint: 2026-10-28

- Commits 3b43110, f7033a1 and 4b9daa3 implement the pytest11 plugin, scenario_run fixture, selected-field observations, explicit inprocess/protected execution, per-case artifacts, controller JSON/Markdown reporting, registered-secret redaction and local xdist crash/replacement handling. The distribution requires pytest and pytest-xdist. Old engine modules are absent from the new source tree; the existing published engine revision remains installable.
- Twenty-three focused runtime checks passed with Python 3.13.16, pytest 9.0.3 and xdist 3.8.0; all twenty-three passed from an independently installed wheel with pytest 9.2.0. Checks include long-node-ID path bounds and deselection under -k, markers and --deselect in both serial and worker modes. Deselected cases are excluded from the report; selected cases stopped before execution remain incomplete. Final wheel SHA256: f72a01d22e1b2e289bc0bba7a2363efd7ee00f4bb84d596c83ea82f83300eb26. Installed verification log: /tmp/scenario-harness-final-wheel/installed-runtime-checks.txt.
- Real consumer code in examples/notes_app uses HTTP, SQLite persistence and semantic observations. An independently installed wheel passed two consumer cases in both protected and inprocess modes; the opt-in negative control failed at its deliberately incorrect expectation. See commit 7a36d84.
- Five skill drafts and installation/usage text are reviewable in pytest-skills-documentation-draft.md (4703d49). Extracted draft skill metadata validates. An independent Sol trial used the drafts to plan a real HTTP acceptance condition, observe missing length validation, implement only the temporary consumer handler and obtain green with the unchanged acceptance case. It rejected an oracle weakened to accept the faulty response and diagnosed an intentional event mismatch followed by real same-worker recovery. Evidence: /tmp/scenario-skill-trial-20261028/skill-trial-report.md. The trial exposed two draft improvements, now included: retain the oracle source/digest and distinguish finalizer completion from actual application cleanup. Skill installation/discovery, asynchronous adoption trials and exact public draft approval remain pending.
- AssistantMD's staged four-case real-application pilot passed against the final installed wheel (90.83 seconds), with application shutdown observed for every case. Its explicitly selected fault profile repeated against that wheel (23.08 seconds) retained the genuine sqlite3.DatabaseError, survived SIGABRT with a replacement worker, and recorded two expected failures followed by their successful recoveries. The application dependency has not switched.
- Hard-hang timeout and descendant-process cleanup are not provided by this checkpoint. The report declares those limits. They remain release/cutover decisions requiring implementation or explicit acceptance, rather than inferred parity with the old runner. Remote workers and dist=each are rejected.

Remaining work includes timeout/descendant-cleanup evaluation, broader repeated/reordered consumer lifecycle proof, additional asynchronous skill exercises, approved public documentation and authorized release preparation and downstream cutover. No remote push, release or application cutover has occurred.

Companion application plan: AssistantMD/pytest-scenario-library-refactor-plan.md. The generic package must become independently usable before AssistantMD switches its pinned dependency or removes its current integration.

## Core methodology skill revision: 2026-10-28

Rename the draft authoring skill to test-application-behavior and update its YAML description and adoption reference. Lead with the purpose of scenario-based testing, stable behavior across implementation changes, real application outputs, semantic internal observations and an independent basis for correctness. The application developer chooses how to expose internal state, for example through structured logs; the plugin supplies observation recording/querying, not application instrumentation. Put pytest/plugin mechanics after the methodology.

The blind AssistantMD trial produced a useful real-app scenario but exposed a judgment failure: the author narrowed an input after an unexpected root-protection failure and inferred correctness from the current implementation. The revised draft explicitly preserves the original failing example, treats changed inputs and omitted cases as changes to proof scope, distinguishes characterization from accepted correctness and requires an independent rationale for correcting an expectation. Historical trial inputs and reports remain unchanged. All five extracted draft packages pass skill metadata validation, and the renamed skill's active path, invocation and plan references agree. A fresh blind Sol authoring trial on the same AssistantMD production snapshot passed its baseline and final real-app runs, explicitly labelled source-derived outcomes as characterization and retained actual file/tool/event evidence. It encountered no behavioral failure, so handling of a failing contract remains untested by that rerun. Evidence and evaluator limits: AssistantMD/validation/runs/skill_evaluations/directory_delete_revised_skill_20261028_hyol076k/evaluator-assessment.md. The earlier dot-path concern remains unresolved.

Scenarios remain ordinary refactorable code. The core and review drafts now guide authors toward a readable state/action/outcome sequence, with setup, evidence serialization, provenance, repetitive diagnostics and routine lifecycle plumbing owned by fixtures or focused helpers. Significant inputs and expectations stay visible; lifecycle actions remain in the journey when lifecycle behavior is the subject. This guidance addresses maintainability without introducing a custom DSL or treating scenario source as immutable.

A final fresh Sol trial used the readability revision at 7c9ec19 with an independent directory-cleanup requirements document. Its final run retained 4 passing cases and 2 genuine failures for specified root representations. All original acceptance assertions survived documented initialization fixes. Real outputs, all-file-type preservation, semantic observations and separate behavior sequences were stronger than the source-only trials. Remaining presentation polish includes moving the module-level support/provenance helpers out of the scenario file. Evidence: AssistantMD/validation/runs/skill_evaluations/directory_cleanup_requirements_20261028_6qjyjja0/evaluator-assessment.md. This demonstrates appropriate failure preservation in that exercise, not a universal guarantee; adding requirements and changing skill wording are separate experimental changes.

This edits the review draft only. Skill installation/publication, protected product documentation and framework/application behavior remain outside this revision. No full-suite run is needed for the prose change.

## Purpose

Help developers and agents validate application behavior through real application instances, stable observable outcomes and inspectable evidence, using pytest as the execution system. Reduce repeated integration and reporting work while keeping application behavior and policy in the consuming project.

Behavioral testing is a testing approach, not a property guaranteed by a base class. A scenario invokes production entry points and checks application-produced files, API/tool results, persisted state or structured observations. Controlled input fixtures are allowed; mocked application results and assertions on private collaborator call sequences do not establish application behavior.

## Evidence already established

- Four AssistantMD scenarios passed under pytest with the real application: extensionless file edits, settings editors, vault-relative workflows and asynchronous cancellation/rollback.
- File mutation now goes through the production FileWrite tool. Tasks, scheduler state and durable workflow history are read through production ASGI APIs. Sink assertions match semantic event names and selected fields.
- An event-matcher probe tolerated unrelated logger metadata and extra fields while rejecting an incorrect required outcome. A combined assertion/teardown failure retained both failures and still closed the application.
- A real corrupt-settings startup exception was retained with its sqlite3.DatabaseError traceback. A subsequent real app passed in the same worker.
- A running app worker was intentionally aborted. Pytest-xdist marked the case failed, replaced the worker and ran a successful real-app case in the replacement. Controller JSON/Markdown/JUnit and already-written artifacts survived; dead-worker teardown was unconfirmed.
- Evidence anchors in AssistantMD: commits ad5a5b2, b909b71 and fe60474; validation/experiments/pytest_comparison; the crash report under validation/runs/pytest_comparison/20261027_234735_crash_verified_6ey112b5.

These experiments establish feasibility for the tested local configuration. They do not establish hard-hang handling, subprocess-tree cleanup, arbitrary buffered-output survival, remote artifact transfer or reliable shared-process cleanup across the complete application library.

## Ownership

| Owner | Responsibilities |
|---|---|
| Pytest | Collection, execution, assertion reporting, fixture finalization, ordinary capture, standard exit codes and JUnit integration |
| Pytest-xdist | Worker processes, scheduling, crash detection and bounded worker replacement |
| Generic plugin/library | Scenario evidence context, artifact ownership, structured observations, report enrichment and controller aggregation |
| Application fixtures | Real startup/shutdown, isolated storage/configuration, services, credentials, application-defined observation binding and domain actions |
| Application scenarios | Behavioral contract, real actions and stable expected outcomes |
| Application CI/policy | Canonical test locations, admitted cases, profile membership, protected expectations and human authorization |
| Skills | Behavioral planning, authoring, diagnosis and review judgment |

Do not require BaseScenario, ScenarioApp, a validation/main.py entry point or a separate scenario CLI. A convenience abstraction can be added later only if a concrete repeated need justifies it. Keep ordinary pytest fixtures and Python assertions as the initial authoring model.

## Minimal consumer contract

Settle a small public API before implementation. The following names describe the intended shape and remain provisional.

- A function-scoped scenario_run fixture supplies a unique root, an artifacts directory, an observation recorder/query interface, explicit secret registration and small helpers for retaining structured outputs.
- The consuming project's app fixture depends on scenario_run, starts the actual application with run-owned state and connects any chosen application observations to the recorder. Pytest owns fixture finalization.
- Application tests request app and use ordinary assertions. They can access scenario_run directly when necessary; common cases should not repeat context lookup or reporting boilerplate.
- Published event observations have a minimal name/data envelope, optional metadata and an explicit mapping seam for application log formats. Matching uses recursive selected fields, checkpoints and correlation identifiers. Extra diagnostic fields do not invalidate a behavioral expectation.
- Inputs and expected observations are separate. A test emitting its own expected application event is not proof that the application behaved correctly.
- Application API/tool signatures and semantic event fields are unavoidable observation/action contracts. Keep these small and intentional; avoid asserting entire internal snapshots, logger classes, filenames, timestamps or method-call sequences.

A typical adoption should need a dependency, conventional pytest configuration and one application fixture. Configuration must have a small documented purpose; do not reproduce the previous callback/project-configuration framework through pytest options.

## Package and execution policy

- Retain the repository and Python package name initially. Introduce a new pre-1.0 version for the changed contract; 0.2.0 is the proposed next release.
- Declare pytest and pytest-xdist as required package dependencies. Installation must make xdist available without a separate consumer step.
- Worker activation remains explicit project configuration. Recommend one sequential worker initially, a bounded restart allowance and additional workers only after the application proves safe parallel execution.
- When scenario mode promises crash protection, validate that workers are enabled. Provide an explicit in-process debugging mode whose report identifies the reduced protection. Installing the plugin must not silently parallelize unrelated tests.
- Keep the generic package neutral about an application's asynchronous fixture provider. The async example and package tests can use pytest-asyncio; AssistantMD declares the async testing dependency it needs.
- Register a standard pytest plugin entry point. Remove the standalone command and module runner from the new distribution.
- Start with tested Python 3.13 compatibility. The experiments used pytest 9.0.3 and xdist 3.8.0. Choose supported dependency ranges from CI evidence rather than claiming untested versions/platforms.
- Preserve old published Git revisions and avoid history rewriting. AssistantMD's current a066ef6 pin continues to identify the old engine until the application migration deliberately changes it. Old and new code share the distribution name: pilot them in separate environments rather than shipping two engines in the new package. Preserve credential/build ignore rules during the source teardown.

## Evidence and reliability contract

1. Give each selected scenario distinct artifact ownership and every worker a separate namespace. The controller owns the final run summary and records all selected cases, including cases not executed after interruption or worker loss.
2. Preserve pytest's actual phase verdicts and session exit code. Worker-attached metadata enriches evidence; it must not manufacture a passing outcome when pytest reports failure. Do not convert crashes into successful retries.
3. Record setup, call and teardown outcomes, exception type/summary/traceback, captured output, worker identity and artifact references. Preserve concurrent execution/cleanup failures.
4. Distinguish Python exceptions from abrupt process termination. A native crash has no Python exception object. Attach genuine fatal-signal diagnostics where available and identify missing diagnostics honestly.
5. Mark cleanup completed, failed or unconfirmed from available evidence. Process death cannot establish successful application teardown.
6. Persist application observations and important artifacts during execution so already-written evidence survives worker loss. State the limits of buffered stdout/stderr and do not promise universal lossless capture.
7. Provide useful JSON and Markdown summaries alongside pytest/JUnit output. Use an explicit, versioned report identity rather than silently reusing the old engine's schema or exit-code meanings.
8. Make artifact location, retention and upload policy explicit. Do not remove previous application data or evidence through implicit cleanup. Retention must stay inside plugin-owned directories.
9. Redact explicitly registered values in plugin-owned output. Test forwarded phase reports, JSON, Markdown and JUnit boundaries. Raw application files need their own declared policy; no automatic discovery of production credentials.
10. Prove serial debugging and local xdist execution independently. Remote workers and distribution modes that execute the same node on multiple workers remain unsupported until ownership/aggregation is tested.

## Skills to deliver

Skills ship as focused, discoverable SKILL.md packages with progressive references and examples where useful. Avoid duplicating the API manual or adding general programming advice. Installation of the Python package must not silently modify agent configuration or install skills into a user's home directory.

| Proposed skill | Trigger and outcome |
|---|---|
| plan-behavioral-change | Turn a feature/change request into observable contracts, a coverage decision and an implementation plan with meaningful red/green evidence |
| integrate-scenario-testing | Install/configure the plugin and create real application fixtures, observation bindings and project CI policy |
| test-application-behavior | Teach the behavioral testing methodology, stable correctness contracts and failure investigation, then apply it through real-app scenarios and the red/green/refactor loop |
| review-behavioral-scenarios | Assess semantic coverage, private-interface coupling, mocks, weakened expectations, admission and the quality of evidence |
| diagnose-scenario-failures | Interpret application failures, fixture errors, worker loss and artifacts; reproduce the smallest relevant case without hiding faults |

Names and boundaries may be consolidated after realistic trials. Keep planning an explicit supported capability even if the final skills are packaged differently.

### Required behavior-first planning workflow

The planning skill must support a practical TDD-like workflow, not merely give advice to write tests first.

1. Identify the requested observable behavior, relevant production entry point, permitted inputs, expected state transitions and important failure cases. Record assumptions and open specification questions before implementation.
2. Inspect existing scenarios and coverage records. Decide whether to extend a scenario, add one or use a narrower check; do not require a new scenario for every incidental implementation change.
3. Define the smallest stable observations that discriminate success from failure: real output, persisted state or meaningful application events. Define event semantics and minimum fields when instrumentation is necessary.
4. Plan real application startup, isolated state and dependencies. Identify live-service requirements, timing costs and unavailable inputs. Do not fill missing services with mocked results and call the result full-stack proof.
5. Write the implementation plan around an executable behavioral acceptance condition. Include the relevant scenario selection, the expected red outcome, implementation steps, green verification, evidence locations and any project-specific approvals.
6. Implement the scenario and observe a meaningful failure before adding the behavior. Explain why that failure demonstrates the missing behavior; unrelated configuration/import/setup failures are not useful red evidence.
7. Implement the real application change, then rerun the same scenario to obtain green evidence. Preserve the original expectation unless the intended behavior is explicitly revised and reviewed.
8. Refactor while keeping the behavioral oracle stable. Application integration helpers may adapt to changed entry points; scenario assertions should continue to describe outcomes rather than private execution strategies.
9. Review negative cases, meaningful failure discrimination, artifacts and known coverage limits. Run broader profiles according to project cadence and authorization, not automatically after every edit.

For migration of already-working behavior, establish a real green baseline and use clearly labelled negative controls to validate expectations. Do not invent a product defect or present an incorrect-expectation probe as proof of a production implementation mutation.

Skills guide agents; they do not grant permissions, bypass repository instructions or mechanically prove semantic test quality. Respect each consuming project's authorization and documentation rules.

## Implementation sequence

### Phase 1: Freeze the small public contract

- Define the scenario_run fixture, event envelope/query semantics, activation/scope rules, report schema and worker/debug policy.
- Classify each module of the old repository as replace, reuse narrowly, move to an application owner or delete. Reuse tested pure functions where useful; do not retain a second execution architecture for compatibility.
- Identify AssistantMD dependencies on old governance APIs and coordinate their project-owned replacement before its dependency switch.
- Write an adoption example and evaluate its setup burden before expanding the API. Keep unproved hard-hang/environment guarantees explicit.

Exit: a concise consumer contract and a module disposition list with release-blocking requirements identified.

### Phase 2: Build the plugin foundation

- Port/refine the tested reporting and observation mechanisms from the AssistantMD experiment.
- Implement standard plugin loading and dependency declarations, fixture-owned artifact resources and worker/controller aggregation.
- Remove the separate collection/execution/worker/CLI implementation and its obsolete fixtures/tests from the new source tree. Replace old engine-specific tests with tests of the new contract.
- Keep project-specific registry approvals and GitHub reviewer policy outside the generic plugin. Preserve only small runner-neutral helpers if a demonstrated consumer need warrants them.

Exit: an installed wheel can validate a separate application without AssistantMD imports, repository-path injection or the old engine.

### Phase 3: Validate runtime guarantees and scope

- Use pytest's plugin-testing facilities and small real fixture applications for sync/async output, observations, phase errors, worker death and controller persistence.
- Cover benign extra observation fields, wrong expected outcomes, redaction boundaries, report/pytest verdict consistency, skipped/interrupted/unstarted cases and multiple selected tests after a fault.
- Preserve the proven startup-exception and native-abort/recovery tests. Distinguish expected fault-run exit 1 from successful recovery verification.
- Test at least two local workers for artifact collision/aggregation, in addition to the proven sequential worker/replacement case.
- Run repeated and reordered application lifecycles in reused workers, including startup and teardown errors. Measure real cleanup leakage rather than assuming a new object resets process globals.
- Evaluate existing timeout tooling for hung workers and blocked native code, with bounded verification and honest cleanup status. Investigate descendant-process cleanup separately. Choose and document the minimum release guarantees; do not silently drop a guarantee required by the application migration.
- Keep assertions about unsupported remote workers, platforms or distribution modes out of the published contract.

Exit: documented guarantees match observed results, and remaining limits are explicitly accepted before downstream cutover.

### Phase 4: Deliver skills, examples and documentation

- Implement the focused skills, including the behavior-first planning workflow. Use one authoritative API reference and small reusable examples.
- Validate skill metadata/references and evaluate realistic requests in isolated fixture projects. Use independent agent trials when authorized; judge produced scenarios and evidence, not literal wording matches.
- Demonstrate a new feature's genuine red/green loop, an implementation refactor that preserves outcomes, a wrongly weakened oracle rejected by review/policy and a diagnosed application/worker failure.
- Document dependency installation, project configuration, the app fixture, evidence/secret boundaries, xdist/debug modes, CI use and editable sibling development.
- Define a supported skill installation path. Skill delivery is explicit and separate from Python package installation.

Exit: another developer can install the package and start a real app scenario using the example and skills without reconstructing hidden infrastructure.

### Phase 5: Release and downstream pilot

- Build and install the wheel in a clean environment outside both repositories. Run the reference applications and plugin self-checks from that installed distribution.
- Publish a tested immutable revision or release without rewriting the old engine history. No PyPI publication, license change or remote push is implied by this planning task.
- Let the companion AssistantMD plan validate the installed package with its real application cases and gate the dependency switch. Keep generic implementation ownership in this repository.

Exit: release evidence, supported versions and the downstream pilot are reviewable; the old engine has no place in the new distribution unless a specific reuse was justified.

## Completion criteria

- Standard pytest is the sole test execution path; xdist supplies worker management.
- A small real-app fixture and conventional test configuration are sufficient for adoption.
- Semantic outputs and selected observations remain the assertion boundary; no required custom scenario class or authoring DSL exists.
- Failure, crash, cleanup and incomplete-execution evidence is accurate and inspectable.
- Skills cover planning as well as authoring, review and diagnosis, with meaningful red/green evidence.
- No AssistantMD imports, paths, event names, domain helpers or reviewer identities enter the generic package.
- Runtime code, skills, examples and release tests describe the same supported contract.

## Documentation review before publication

Draft the new README, public API/evidence reference and each SKILL.md for review before applying/publishing them. Keep the product documentation about the new current contract; migration details belong in the companion implementation plans unless explicitly requested for publication. Review the drafts and affected files with the user, obtain explicit approval, apply the approved text and validate the packaged documentation/skill resources. AssistantMD guide changes are separately owned by the companion plan.
