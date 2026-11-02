import json

import pytest

from scenario_harness import ScenarioRun


@pytest.mark.parametrize("register_before", [True, False])
def test_secret_registration_preserves_observation_identity(tmp_path, register_before):
    run = ScenarioRun(tmp_path)
    tokens = ("token-alpha", "token-beta")
    if register_before:
        run.register_secret(*tokens)
    run.record(
        "token-alpha",
        {"nested": {"token-alpha": "token-alpha"}, "items": ["token-alpha"]},
    )
    run.record("literal", {"token": "[REDACTED]"})
    if not register_before:
        run.register_secret(*tokens)

    observations = run.observations
    assert (
        observations.require("token-alpha", nested={"token-alpha": "token-alpha"})[
            "name"
        ]
        == "token-alpha"
    )
    assert observations.contains("token-alpha", fields={"items": ["token-alpha"]})
    assert not observations.contains("token-beta")
    assert not observations.contains("[REDACTED]")
    assert not observations.contains(
        "token-alpha", fields={"nested": {"token-beta": "token-alpha"}}
    )
    assert not observations.contains(
        "token-alpha", fields={"nested": {"token-alpha": "token-beta"}}
    )
    assert not observations.contains("token-alpha", fields={"items": ["token-beta"]})
    assert observations.contains("literal", fields={"token": "[REDACTED]"})
    assert not observations.contains("literal", fields={"token": "token-alpha"})
    with pytest.raises(AssertionError) as caught:
        observations.require("token-alpha", fields={"items": ["token-beta"]})
    run.save_json("selected.json", observations.select())
    for exported in (
        str(caught.value),
        (run.artifacts / "selected.json").read_text(),
        (run.artifacts / "event-assertions.jsonl").read_text(),
    ):
        assert all(token not in exported for token in tokens)


def test_caller_mutations_cannot_rewrite_captured_evidence(tmp_path):
    run = ScenarioRun(tmp_path)
    source = {
        "name": "ready",
        "data": {"nested": {"values": [1, 2]}},
        "metadata": {"tags": ["original"]},
    }
    run.observations.capture(source)
    source["data"]["nested"]["values"].append(3)
    source["metadata"]["tags"].clear()
    source["name"] = "changed"
    selected = run.observations.select("ready")
    selected[0]["data"]["nested"]["values"].clear()
    selected[0]["metadata"]["tags"].append("changed")
    required = run.observations.require("ready", nested={"values": [1, 2]})
    required["data"]["nested"]["values"].append(9)
    assert run.observations.select("ready") == [
        {
            "name": "ready",
            "data": {"nested": {"values": [1, 2]}},
            "metadata": {"tags": ["original"]},
        }
    ]
    assert (
        json.loads((run.artifacts / "observations.jsonl").read_text())
        == run.observations.select("ready")[0]
    )


def test_wrong_secret_fails_with_safe_diagnostics_and_artifacts(tmp_path):
    run = ScenarioRun(tmp_path)
    run.register_secret(
        "event-secret", "actual-token", "wrong-token", "key-secret", "escaped\nsecret"
    )
    run.record("event-secret", {"key-secret": {"token": "actual-token"}})
    assert (
        run.observations.require(
            "event-secret", fields={"key-secret": {"token": "actual-token"}}
        )["data"]["key-secret"]["token"]
        == "actual-token"
    )
    with pytest.raises(AssertionError) as caught:
        run.observations.require(
            "event-secret", fields={"key-secret": {"token": "wrong-token"}}
        )
    with pytest.raises(AssertionError) as escaped:
        run.observations.require(
            "escaped\nsecret", fields={"escaped\nsecret": "escaped\nsecret"}
        )
    diagnostic = str(caught.value) + str(escaped.value)
    assert "Missing application event" in diagnostic
    assert "[REDACTED]" in diagnostic
    for secret in (
        "event-secret",
        "actual-token",
        "wrong-token",
        "key-secret",
        "escaped",
        "escaped\\nsecret",
    ):
        assert secret not in diagnostic
    for artifact in run.artifacts.iterdir():
        content = artifact.read_text()
        assert "[REDACTED]" in content
        for secret in (
            "event-secret",
            "actual-token",
            "wrong-token",
            "key-secret",
            "escaped\\nsecret",
        ):
            assert secret not in content
    assertions = [
        json.loads(line)
        for line in (run.artifacts / "event-assertions.jsonl").read_text().splitlines()
    ]
    assert [item["matched"] for item in assertions] == [True, False, False]
