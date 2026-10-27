"""/people runs the deployment's hook with validated argv, one at a time."""
from __future__ import annotations

import json
import os
import stat

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

H = {"X-API-Key": os.environ["HERMES_BRIDGE_API_KEY"]}


@pytest.fixture
def hook(tmp_path, monkeypatch):
    log = tmp_path / "argv.jsonl"
    script = tmp_path / "hook"
    script.write_text(f"""#!/usr/bin/env python3
import json, sys
open({str(log)!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[2] == "boom":
    print("\\x1b[1;31m[kit]\\x1b[0m unknown tenant(s) nosuch", file=sys.stderr); sys.exit(1)
out = {{"matrix_id": "@" + sys.argv[2] + ":hs.test"}}
if sys.argv[1] == "add":
    out["initial_password"] = "pw-123"
print("noise"); print(json.dumps(out))
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(settings, "people_hook", str(script))
    return lambda: [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


def test_add_update_remove_pass_validated_argv(hook):
    c = TestClient(app)
    r = c.post("/people", headers=H, json={"localpart": "ana", "name": "Ana Example",
                                           "tenants": ["sales", "marketing", "sales"], "approve": ["sales"]})
    assert r.status_code == 200 and r.json() == {"ok": True, "matrix_id": "@ana:hs.test", "initial_password": "pw-123"}
    assert c.put("/people/ana", headers=H, json={"tenants": ["tech"]}).json()["initial_password"] is None
    assert c.delete("/people/ana", headers=H).status_code == 200
    assert hook() == [["add", "ana", "Ana Example", "sales,marketing", "sales"],
                      ["update", "ana", "tech", "-"], ["remove", "ana"]]


def test_language_rides_along_only_when_given_and_has_its_own_route(hook):
    c = TestClient(app)
    assert c.post("/people", headers=H, json={"localpart": "ana", "name": "Ana", "tenants": ["tech"], "language": "de"}).status_code == 200
    assert c.put("/people/ana", headers=H, json={"tenants": ["tech"], "language": "en"}).status_code == 200
    assert c.put("/people/ana/language", headers=H, json={"language": "de"}).status_code == 200
    assert c.put("/people/ana/language", headers=H, json={"language": ""}).status_code == 200
    assert c.put("/people/ana/language", headers=H, json={"language": "de-CH"}).status_code == 422
    assert c.put("/people/ana", headers=H, json={"tenants": ["tech"], "language": "x;y"}).status_code == 422
    assert hook() == [["add", "ana", "Ana", "tech", "-", "de"], ["update", "ana", "tech", "-", "en"],
                      ["language", "ana", "de"], ["language", "ana", "-"]]


@pytest.mark.parametrize("body", [
    {"localpart": "Ana", "name": "A", "tenants": ["tech"]},
    {"localpart": "ana;rm", "name": "A", "tenants": ["tech"]},
    {"localpart": "ana", "name": 'A"b', "tenants": ["tech"]},
    {"localpart": "ana", "name": "A", "tenants": []},
    {"localpart": "ana", "name": "A", "tenants": ["--force"]},
    {"localpart": "ana", "name": "A", "tenants": ["tech"], "approve": ["a,b"]},
])
def test_bad_input_never_reaches_the_hook(hook, body):
    assert TestClient(app).post("/people", headers=H, json=body).status_code == 422
    assert hook() == []


def test_hook_errors_come_back_without_colour_codes(hook):
    r = TestClient(app).post("/people", headers=H, json={"localpart": "boom", "name": "B", "tenants": ["tech"]})
    assert r.status_code == 400 and r.json()["detail"] == "[kit] unknown tenant(s) nosuch"


def test_refused_without_hook_and_without_key(monkeypatch):
    monkeypatch.setattr(settings, "people_hook", None)
    c = TestClient(app)
    assert c.delete("/people/ana", headers=H).status_code == 503
    assert c.delete("/people/ana").status_code == 401
