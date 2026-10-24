"""Run the bridge against scripts/stub_hermes, which parses the real CLI's
argument shapes; each test gets a fresh stub database and argv log."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

STUB = Path(__file__).resolve().parents[1] / "scripts" / "stub_hermes"
os.environ.setdefault("HERMES_BRIDGE_API_KEY", "test-key")
os.environ["HERMES_BRIDGE_HERMES_BIN"] = str(STUB)

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


class Stub:
    def __init__(self, tmp: Path):
        self.db = tmp / "stub.db"
        self.log = tmp / "argv.jsonl"

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def status(self, task_id: str) -> str:
        with sqlite3.connect(self.db) as conn:
            return conn.execute("select status from tasks where id=?", (task_id,)).fetchone()[0]

    def comments(self, task_id: str) -> list[tuple[str, str]]:
        with sqlite3.connect(self.db) as conn:
            return conn.execute("select author, body from comments where task_id=?", (task_id,)).fetchall()


@pytest.fixture
def stub(tmp_path, monkeypatch) -> Stub:
    s = Stub(tmp_path)
    monkeypatch.setenv("STUB_DB", str(s.db))
    monkeypatch.setenv("STUB_LOG", str(s.log))
    monkeypatch.setattr(settings, "kanban_board", "testboard")
    return s


@pytest.fixture
def client(stub) -> TestClient:
    return TestClient(app, headers={"X-API-Key": settings.api_key})


@pytest.fixture
def create(client):
    def _create(status: str = "ready", **extra) -> str:
        r = client.post("/kanban/tasks", json={"title": "T", "tenant": "tech", "status": status, **extra})
        assert r.status_code == 200, r.text
        return json.loads(r.json()["detail"])["id"]
    return _create
