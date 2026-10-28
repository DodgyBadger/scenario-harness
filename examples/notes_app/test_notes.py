"""Run from repository root: pytest examples/notes_app --scenario-mode protected -n 1."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

pytestmark = pytest.mark.scenario


def request(app, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    try:
        response = urlopen(Request(app.url + path, data=data, headers={"Content-Type": "application/json"}), timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def test_created_note_is_readable(app, scenario_run):
    checkpoint = scenario_run.observations.checkpoint()
    status, note = request(app, "/notes", {"text": "  hello  "})
    assert status == 201
    assert note["text"] == "hello"
    assert request(app, f"/notes/{note['id']}") == (200, note)
    scenario_run.observations.require("note.created", fields={"note_id": note["id"], "text": "hello"}, after=checkpoint)
    scenario_run.save_json("created-note.json", note)


def test_empty_note_is_rejected(app, scenario_run):
    checkpoint = scenario_run.observations.checkpoint()
    assert request(app, "/notes", {"text": " "}) == (422, {"error": "text is required"})
    scenario_run.observations.require("note.rejected", fields={"reason": "empty_text"}, after=checkpoint)
    assert not scenario_run.observations.contains("note.created", after=checkpoint)
    assert request(app, "/notes/1")[0] == 404


def test_wrong_expected_event_demonstrates_failure(explicit_faults, app, scenario_run):
    """Negative control, not evidence of a product defect or a red/green change."""
    status, note = request(app, "/notes", {"text": "actual"})
    assert status == 201
    scenario_run.observations.require("note.created", fields={"note_id": note["id"], "text": "incorrect expectation"})
