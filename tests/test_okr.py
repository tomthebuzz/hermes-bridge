"""/okr: writes to the team store through its CLI wrapper, validated here
with a fake wrapper that records the calls and answers like the store."""
from __future__ import annotations

import json

import pytest

from app.config import settings
from app.domains.okr import service


@pytest.fixture
def store(monkeypatch):
    calls: list[tuple[str, ...]] = []
    objects = {"keyresult_abc123": {"id": "keyresult_abc123", "type": "KeyResult", "data": {"title": "Leads", "current": 3}},
               "kpi_abc123": {"id": "kpi_abc123", "type": "KPI", "data": {"title": "Open", "current": 9}},
               "objective_abc123": {"id": "objective_abc123", "type": "Objective", "data": {"tenant": "tech"}},
               "kpi_f0110a5": {"id": "kpi_f0110a5", "type": "KPI", "data": {"tenant": "tech", "objective": "objective_abc123"}},
               "swimlane_01d001": {"id": "swimlane_01d001", "type": "Swimlane", "data": {"tenant": "tech", "name": "Speed", "objective": "objective_abc123"}}}

    def fake_run(*args):
        calls.append(args)
        a = dict(zip(args[1::2], args[2::2]))
        if args[0] == "get":
            o = objects.get(a["--id"])
            return service.StoreResult(True, o) if o else service.StoreResult(False, error=f"no object '{a['--id']}'")
        if args[0] == "upsert":
            oid = a.get("--id") or f"{a['--type'].lower()}_{len(calls):06x}"
            o = objects.setdefault(oid, {"id": oid, "type": a["--type"], "data": {}})
            o["data"].update(json.loads(a["--data"]))
            return service.StoreResult(True, o)
        if args[0] == "link":
            return service.StoreResult(True, {"rel": a["--rel"], "from": a["--from"], "to": a["--to"]})
        if args[0] == "delete":
            return service.StoreResult(True, {"deleted": a["--id"]})
        if args[0] == "search":
            items = [o for o in objects.values() if o["type"] == a["--type"] and a.get("--text", "") in json.dumps(o["data"])]
            return service.StoreResult(True, {"count": len(items), "items": items})
        raise AssertionError(args)

    monkeypatch.setattr(service, "_run", fake_run)
    monkeypatch.setattr(settings, "team_store_cli", "/fake/store")
    return calls, objects


def test_refused_without_a_store(client, monkeypatch):
    monkeypatch.setattr(settings, "team_store_cli", None)
    r = client.post("/okr/objects", json={"type": "KPI", "data": {}, "actor": "a", "reason": "r"})
    assert r.status_code == 503


def test_create_key_result_links_it_to_the_objective(client, store):
    calls, objects = store
    r = client.post("/okr/objects", json={"type": "KeyResult", "objective_id": "objective_abc123",
                                          "data": {"title": "Cycle​ time", "target": 24}, "actor": "Anna", "reason": "dashboard"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sanitized"] is True and body["object"]["data"]["title"] == "Cycle time"
    assert calls[0][0] == "upsert" and "--source" in calls[0] and "--actor" in calls[0]
    assert calls[1][:7] == ("link", "--rel", "key_results", "--from", "objective_abc123", "--to", body["object"]["id"])


def test_new_key_result_needs_an_objective_and_types_are_limited(client, store):
    assert client.post("/okr/objects", json={"type": "KeyResult", "data": {}, "actor": "a", "reason": "r"}).status_code == 422
    assert client.post("/okr/objects", json={"type": "Measurement", "data": {}, "actor": "a", "reason": "r"}).status_code == 422
    assert client.post("/okr/objects", json={"type": "KPI", "data": {}, "actor": "", "reason": "r"}).status_code == 422


def test_update_passes_the_id_and_no_source(client, store):
    calls, _ = store
    r = client.post("/okr/objects", json={"type": "KPI", "id": "kpi_abc123", "data": {"target": 5}, "actor": "Anna", "reason": "edit"})
    assert r.status_code == 200 and "--id" in calls[0] and "--source" not in calls[0]


def test_checkin_writes_measurement_link_and_current(client, store):
    calls, objects = store
    r = client.post("/okr/checkin", json={"target_id": "keyresult_abc123", "value": 7, "note": "fair", "actor": "Anna", "reason": "weekly check-in"})
    assert r.status_code == 200, r.text
    kinds = [c[0] for c in calls]
    assert kinds == ["get", "upsert", "link", "upsert"]
    m = json.loads(dict(zip(calls[1][1::2], calls[1][2::2]))["--data"])
    assert m["method"] == "manual" and m["actor"] == "Anna" and m["value"] == 7 and m["note"] == "fair" and m["at"].endswith("Z")
    assert calls[2][2] == "kr_measurements"
    assert objects["keyresult_abc123"]["data"]["current"] == 7 and "last_checkin" in objects["keyresult_abc123"]["data"]
    r = client.post("/okr/checkin", json={"target_id": "kpi_abc123", "value": 1, "actor": "Anna", "reason": "x"})
    assert r.status_code == 200 and objects["kpi_abc123"]["data"]["current"] == 1


def test_checkin_on_unknown_target_is_a_502(client, store):
    r = client.post("/okr/checkin", json={"target_id": "kpi_000000", "value": 1, "actor": "Anna", "reason": "x"})
    assert r.status_code == 502 and "no object" in r.json()["detail"]


def test_delete(client, store):
    calls, _ = store
    r = client.post("/okr/objects/objective_abc123/delete", json={"actor": "Anna", "reason": "cleanup"})
    assert r.status_code == 200 and calls[0][:3] == ("delete", "--id", "objective_abc123")


def test_move_objective_takes_its_kpis_and_unlinks_old_lanes(client, store):
    calls, objects = store
    r = client.post("/okr/objects/objective_abc123/move", json={"tenant": "ops", "actor": "Anna", "reason": "belongs to ops"})
    assert r.status_code == 200, r.text
    assert objects["objective_abc123"]["data"]["tenant"] == "ops"
    assert objects["kpi_f0110a5"]["data"]["tenant"] == "ops" and objects["kpi_f0110a5"]["data"]["objective"] == "objective_abc123"
    assert objects["swimlane_01d001"]["data"]["objective"] is None and objects["swimlane_01d001"]["data"]["tenant"] == "tech"
    assert r.json()["object"]["moved"] == {"kpis": ["kpi_f0110a5"], "lanes_unlinked": ["swimlane_01d001"]}


def test_move_kpi_alone_leaves_its_objective_and_key_results_cannot_move(client, store):
    calls, objects = store
    r = client.post("/okr/objects/kpi_f0110a5/move", json={"tenant": "ops", "actor": "Anna", "reason": "x"})
    assert r.status_code == 200 and objects["kpi_f0110a5"]["data"] == {"tenant": "ops", "objective": None}
    assert client.post("/okr/objects/keyresult_abc123/move", json={"tenant": "ops", "actor": "Anna", "reason": "x"}).status_code == 502
    assert client.post("/okr/objects/objective_abc123/move", json={"tenant": "tech", "actor": "Anna", "reason": "x"}).status_code == 502
    assert client.post("/okr/objects/objective_abc123/move", json={"tenant": "Bad Team", "actor": "Anna", "reason": "x"}).status_code == 422
