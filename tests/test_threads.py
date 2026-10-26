"""One Matrix thread per card: the tenant's bot posts the card, Hermes'
events are subscribed to the thread, Portal actions are posted into it with
the stakeholders' names, and the thread is kept in the team store."""
from __future__ import annotations

import json

import pytest

from app.config import settings
from app.domains.okr import service as team_store


@pytest.fixture
def routed(tmp_path, monkeypatch):
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"tech": {"platform": "matrix", "chat_id": "!tech:hs", "chat_type": "group", "notifier_profile": "tech"},
                                  "sales": {"platform": "matrix", "chat_id": "!sales:hs"}}))   # no bot: plain subscription
    monkeypatch.setattr(settings, "notify_routes_file", str(routes))


@pytest.fixture
def store(monkeypatch):
    objects: dict = {}
    calls: list = []

    def fake_run(*args):
        calls.append(args)
        a = dict(zip(args[1::2], args[2::2]))
        if args[0] == "upsert":
            oid = a.get("--id") or f"{a['--type'].lower()}_{len(objects) + 1:06x}"
            o = objects.setdefault(oid, {"id": oid, "type": a["--type"], "data": {}})
            o["data"].update(json.loads(a["--data"]))
            return team_store.StoreResult(True, o)
        if args[0] == "search":
            items = [o for o in objects.values() if o["type"] == a["--type"] and (not a.get("--text") or a["--text"] in json.dumps(o["data"]))]
            return team_store.StoreResult(True, {"count": len(items), "items": items})
        raise AssertionError(args)
    monkeypatch.setattr(team_store, "_run", fake_run)
    monkeypatch.setattr(settings, "team_store_cli", "/fake/store")
    return objects, calls


def sends(stub):
    return [c for c in stub.calls() if "send" in c[:3]]


def test_card_gets_a_thread_in_its_room(client, stub, routed, store, create):
    objects, _ = store
    task_id = create(tenant="tech", title="Fix the build")
    s = sends(stub)
    assert s and s[0][:2] == ["-p", "tech"] and s[0][-1] == f"Task {task_id}: Fix the build" and "--json" in s[0]
    sub = next(c for c in stub.calls() if "notify-subscribe" in c)
    assert any(x.startswith("--thread-id=$stub-") for x in sub) and "--chat-type=thread" in sub and "--parent-chat-id=!tech:hs" in sub
    threads = [o for o in objects.values() if o["type"] == "TaskThread"]
    assert len(threads) == 1 and threads[0]["data"]["task_id"] == task_id and threads[0]["data"]["event_id"].startswith("$stub-")


def test_room_without_a_bot_keeps_the_plain_subscription(client, stub, routed, store, create):
    create(tenant="sales")
    assert not sends(stub)
    sub = next(c for c in stub.calls() if "notify-subscribe" in c)
    assert "--chat-id=!sales:hs" in sub and not any(x.startswith("--thread-id") for x in sub)


def test_portal_actions_are_posted_into_the_thread_with_stakeholders(client, stub, routed, store, create):
    objects, _ = store
    task_id = create(tenant="tech", title="T")
    objects["tasklink_1"] = {"id": "tasklink_1", "type": "TaskLink", "data": {"task_id": task_id, "person": "Anna Keller", "role": "reviewer"}}
    objects["tasklink_2"] = {"id": "tasklink_2", "type": "TaskLink", "data": {"task_id": "t_other", "person": "Nobody", "role": "watcher"}}
    thread = next(o for o in objects.values() if o["type"] == "TaskThread")["data"]["event_id"]
    assert client.post(f"/kanban/tasks/{task_id}/comments", json={"text": "looks fine", "author": "Tom"}).status_code == 200
    assert client.post(f"/kanban/tasks/{task_id}/comments", json={"text": "mine", "author": "Anna Keller"}).status_code == 200
    assert client.post(f"/kanban/tasks/{task_id}/transition", json={"status": "blocked", "current_status": "ready", "reason": "waiting"}).status_code == 200
    posts = sends(stub)[1:]
    assert all(c[c.index("--to") + 1] == f"matrix:!tech:hs:{thread}" for c in posts)
    assert posts[0][-1] == "Comment: looks fine (Tom) · Anna Keller"
    assert posts[1][-1] == "Comment: mine (Anna Keller)"            # the actor is not pinged
    assert posts[2][-1] == "Moved to blocked: waiting · Anna Keller"
    assert "Nobody" not in posts[0][-1]


def test_no_thread_no_post(client, stub, store, create):
    task_id = create(tenant="tech")
    client.post(f"/kanban/tasks/{task_id}/comments", json={"text": "hi"})
    assert not sends(stub)


def test_review_card_decision_updates_the_review_record(client, stub, store, create):
    objects, calls = store
    task_id = create(tenant="tech", title="Weekly review 2026-W44")
    objects["review_1"] = {"id": "review_1", "type": "Review", "data": {"tenant": "tech", "week": "2026-W44", "kanban_task_id": task_id, "status": "pending"}}
    objects["review_0"] = {"id": "review_0", "type": "Review", "data": {"tenant": "tech", "week": "2026-W43", "kanban_task_id": "t_old", "status": "approved"}}
    assert client.post(f"/kanban/tasks/{task_id}/publish-for-review", json={"summary": "v1"}).status_code == 200
    assert client.post(f"/kanban/tasks/{task_id}/approve", json={"note": "fine", "author": "Tom"}).status_code == 200
    assert objects["review_1"]["data"]["status"] == "approved" and objects["review_0"]["data"]["status"] == "approved"
    upd = [c for c in calls if c[0] == "upsert" and "--id" in c and "review_1" in c]
    assert upd and "Tom" in upd[-1]
