import pytest

from app import NotesApp


def pytest_addoption(parser):
    parser.addoption("--example-faults", action="store_true", help="Run intentional failing example probes")


@pytest.fixture
def app(scenario_run):
    application = NotesApp(scenario_run.root / "notes.sqlite3", scenario_run.observations.record)
    application.start()
    try:
        yield application
    finally:
        application.close()


@pytest.fixture
def explicit_faults(request):
    if not request.config.getoption("--example-faults"):
        pytest.skip("Intentional failure demonstration requires --example-faults")
