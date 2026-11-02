"""Run-owned evidence and selected-field observation queries."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any


def _subset(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and _subset(actual[k], v) for k, v in expected.items()
        )
    return actual == expected


class ScenarioRun:
    def __init__(self, root: Path):
        self.root = root
        self.artifacts = root / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = self.artifacts
        self._secrets: set[str] = set()
        self._lock = RLock()
        self.observations = Observations(self)

    def register_secret(self, *values: str) -> None:
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("Secrets must be nonempty strings")
        self._secrets.update(values)

    def redact(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in sorted(self._secrets, key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {self.redact(str(k)): self.redact(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [self.redact(v) for v in value]
        if value is None or isinstance(value, bool | int | float):
            return value
        return self.redact(str(value))

    def _path(self, name: str) -> Path:
        path = (self.artifacts / name).resolve()
        if not path.is_relative_to(self.artifacts.resolve()):
            raise ValueError("Artifact path must stay inside artifacts")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def append(self, name: str, value: Any) -> None:
        with self._lock, self._path(name).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(self.redact(value), default=str) + "\n")

    def save_json(self, name: str, value: Any) -> None:
        self.write_text(
            name, json.dumps(self.redact(value), indent=2, default=str) + "\n"
        )

    save = save_json

    def write_text(self, name: str, text: str) -> None:
        with self._lock:
            self._path(name).write_text(self.redact(text), encoding="utf-8")

    def step(self, name: str, **data: Any) -> None:
        self.append("timeline.jsonl", {"step": name, **data})

    def record(
        self, name: str, data: dict | None = None, metadata: dict | None = None
    ) -> None:
        self.observations.record(name, data, metadata)


class Observations:
    def __init__(self, run: ScenarioRun):
        self.run = run
        self._records: list[dict] = []
        self._lock = RLock()

    def capture(self, record: dict) -> None:
        if not isinstance(record.get("name"), str) or not isinstance(
            record.get("data", {}), dict
        ):
            raise TypeError("Observation requires a string name and mapping data")
        with self._lock:
            captured = deepcopy(record)
            self.run.append("observations.jsonl", captured)
            self._records.append(captured)

    def record(
        self, name: str, data: dict | None = None, metadata: dict | None = None
    ) -> None:
        self.capture({"name": name, "data": data or {}, "metadata": metadata or {}})

    def checkpoint(self) -> int:
        with self._lock:
            return len(self._records)

    def select(
        self, name: str | None = None, *, fields: dict | None = None, after: int = 0
    ) -> list[dict]:
        if after < 0:
            raise ValueError("Checkpoint must be nonnegative")
        with self._lock:
            return [
                deepcopy(r)
                for r in self._records[after:]
                if (name is None or r["name"] == name)
                and _subset(r.get("data", {}), fields or {})
            ]

    def contains(
        self, name: str, *, fields: dict | None = None, after: int = 0
    ) -> bool:
        return bool(self.select(name, fields=fields, after=after))

    def require(
        self, name: str, *, fields: dict | None = None, after: int = 0, **selected: Any
    ) -> dict:
        expected = {**(fields or {}), **selected}
        matches = self.select(name, fields=expected, after=after)
        self.run.append(
            "event-assertions.jsonl",
            {
                "event": name,
                "expected": expected,
                "after": after,
                "matched": bool(matches),
            },
        )
        if not matches:
            message = (
                f"Missing application event {self.run.redact(name)!r} "
                f"matching {self.run.redact(expected)!r}"
            )
            raise AssertionError(self.run.redact(message))
        return matches[-1]
